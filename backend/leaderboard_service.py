from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue
from typing import Any

from gene_level_core import compute_gff_metric

from .busco_eval import BUSCOEvaluator

PREDICTIONS_REPO_URL = (
    "https://github.com/alexeyshmelev/genatator-leaderboard-predictions.git"
)
TEMP_SUBMISSION_TTL_SECONDS = 30 * 60


def _plain_model_key(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return "".join(ch for ch in text if ch.isalnum())


def _reference_aliases(value: object) -> set[str]:
    text = str(value or "").strip()
    if not text:
        return set()

    aliases = {
        text,
        text.lower(),
        Path(text).name,
        Path(text).name.lower(),
        Path(text).stem,
        Path(text).stem.lower(),
    }

    compact = {_plain_model_key(alias) for alias in aliases}
    aliases.update(alias for alias in compact if alias)
    return {alias for alias in aliases if alias}


def _extract_reference_url(value: object) -> str | None:
    if isinstance(value, str):
        url = value.strip()
        return url or None

    if isinstance(value, dict):
        for key in ("reference_url", "url", "paper_url", "link", "paper"):
            url = value.get(key)
            if isinstance(url, str) and url.strip():
                return url.strip()

    return None


def _lookup_reference_url(
    reference_map: dict[str, str], *candidates: object
) -> str | None:
    for candidate in candidates:
        for alias in _reference_aliases(candidate):
            url = reference_map.get(alias)
            if url:
                return url
    return None


def _display_name_from_mapping(name_map: dict, model_id: str, pred_file: Path) -> str:
    value = name_map.get(model_id)
    if value is None:
        value = name_map.get(pred_file.name)

    if isinstance(value, str) and value.strip():
        return value.strip()

    if isinstance(value, dict):
        display_name = value.get("display_name") or value.get("name") or value.get("label")
        if isinstance(display_name, str) and display_name.strip():
            return display_name.strip()

    return model_id


@dataclass
class LeaderboardState:
    running: bool = False
    stage: str = "idle"
    message: str = ""
    total_models: int = 0
    completed_models: int = 0
    current_model: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    launch_date: float = field(default_factory=time.time)
    gene_rows: list[dict[str, Any]] = field(default_factory=list)
    busco_rows: list[dict[str, Any]] = field(default_factory=list)
    model_name_map: dict[str, str] = field(default_factory=dict)
    model_reference_map: dict[str, str] = field(default_factory=dict)
    queue_length: int = 0
    queue_current: str | None = None
    gene_axis_max: int = 100
    busco_axis_max: int = 275

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "user_gene_rows": [], "user_busco_rows": []}


class LeaderboardService:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.external_dir = root_dir / "external"
        self.pred_repo_dir = self.external_dir / "genatator-leaderboard-predictions"
        self.required_dir = root_dir / "leaderboard_required_files"
        self.runs_dir = root_dir / "leaderboard_runs"
        self._lock = threading.Lock()
        self._state = LeaderboardState()
        self._upload_queue: Queue[dict[str, Any]] = Queue()
        self._submission_jobs: dict[str, dict[str, Any]] = {}
        self._submission_results: dict[str, dict[str, Any]] = {}
        self._submission_errors: dict[str, dict[str, Any]] = {}
        threading.Thread(target=self._upload_worker, daemon=True).start()

    def _cleanup_expired_submissions(self) -> None:
        now = time.time()
        for d in (self._submission_results, self._submission_errors):
            for sid, data in list(d.items()):
                if now - data.get("finished_at", now) > TEMP_SUBMISSION_TTL_SECONDS:
                    d.pop(sid, None)
        for sid, data in list(self._submission_jobs.items()):
            if data.get("status") in {"queued", "running"}:
                continue
            if now - data.get("updated_at", now) > TEMP_SUBMISSION_TTL_SECONDS:
                self._submission_jobs.pop(sid, None)

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._cleanup_expired_submissions()
            return self._state.to_dict()

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._state.running:
                return self._state.to_dict()
            self._state = LeaderboardState(
                running=True,
                stage="Building leaderboard",
                message="Building leaderboard...",
                started_at=time.time(),
            )
        threading.Thread(target=self._run_pipeline, daemon=True).start()
        return self.status()

    def enqueue_submission(self, model_name: str, gff_text: str) -> dict[str, Any]:
        submission_id = str(uuid.uuid4())
        display_name = model_name.strip() or f"user-{submission_id[:8]}"
        model_id = f"temporary::{submission_id}"
        job = {
            "submission_id": submission_id,
            "model_name": display_name,
            "model_id": model_id,
            "gff_text": gff_text,
        }
        with self._lock:
            self._cleanup_expired_submissions()
            self._submission_jobs[submission_id] = {
                "status": "queued",
                "updated_at": time.time(),
                "model_name": display_name,
                "model_id": model_id,
            }
            self._upload_queue.put(job)
            self._state.queue_length = self._upload_queue.qsize()
            position = self._state.queue_length
        return {"submission_id": submission_id, "position": position}

    def submission_status(self, submission_id: str) -> dict[str, Any]:
        with self._lock:
            self._cleanup_expired_submissions()
            if submission_id in self._submission_results:
                return self._submission_results[submission_id]
            if submission_id in self._submission_errors:
                return self._submission_errors[submission_id]
            job = self._submission_jobs.get(submission_id)
            return (
                {"status": job["status"], "submission_id": submission_id}
                if job
                else {"status": "expired", "submission_id": submission_id}
            )

    def _run_pipeline(self) -> None:
        try:
            self.required_dir.mkdir(parents=True, exist_ok=True)
            self.runs_dir.mkdir(parents=True, exist_ok=True)
            true_gff = self.required_dir / "chr20.gff"
            fasta = self.required_dir / "Hs_NC_060944.1.fa"
            lineage = self.required_dir / "lineage" / "mammalia_odb10"
            if not true_gff.exists() or not fasta.exists() or not lineage.exists():
                raise FileNotFoundError(
                    "Missing required files. Put chr20.gff, Hs_NC_060944.1.fa and lineage/mammalia_odb10 into leaderboard_required_files/."
                )
            self._set_state(
                stage="Syncing repository", message="Syncing predictions repository"
            )
            prediction_files, name_map, reference_map = self._sync_predictions_repo()
            self._set_state(
                total_models=len(prediction_files),
                model_name_map=name_map,
                model_reference_map=reference_map,
            )
            busco = BUSCOEvaluator()
            gene_rows = []
            busco_rows = []
            for idx, pred_file in enumerate(prediction_files, start=1):
                model_id = pred_file.stem
                self._set_state(
                    stage="Gene-level metric calculation",
                    current_model=model_id,
                    message=f"Calculating {idx}/{len(prediction_files)}",
                )
                raw = compute_gff_metric(
                    pred_gff=str(pred_file),
                    true_gff=str(true_gff),
                    stratifier="type",
                    types=["mRNA", "lnc_RNA"],
                    segments=["exon", "CDS"],
                ).get("raw_result", {})
                display_name = _display_name_from_mapping(name_map, model_id, pred_file)
                reference_url = _lookup_reference_url(
                    reference_map, model_id, pred_file.stem, pred_file.name, display_name
                )
                row = {
                    "model_id": model_id,
                    "reference_url": reference_url,
                    "lncrna_exon": int((raw.get("lnc_RNA") or [0, 0])[0]),
                    "mrna_exon": int((raw.get("mRNA") or [0, 0])[0]),
                    "mrna_cds": int((raw.get("mRNA") or [0, 0])[1]),
                }
                row["total_score"] = (
                    row["lncrna_exon"] + row["mrna_exon"] + row["mrna_cds"]
                )
                gene_rows.append(row)
                m = max((x["total_score"] for x in gene_rows), default=0)
                self._set_state(
                    completed_models=idx,
                    gene_rows=sorted(
                        gene_rows, key=lambda x: x["total_score"], reverse=True
                    ),
                    gene_axis_max=100 if m <= 100 else m + 100,
                    busco_axis_max=275,
                )
            for idx, pred_file in enumerate(prediction_files, start=1):
                model_id = pred_file.stem
                self._set_state(
                    stage="BUSCO metric calculation",
                    current_model=model_id,
                    message=f"Calculating {idx}/{len(prediction_files)}",
                )
                run_dir = self.runs_dir / model_id
                if run_dir.exists(): shutil.rmtree(run_dir)
                run_dir.mkdir(parents=True, exist_ok=True)
                busco_result = busco.busco_prepare_gff(
                    pred_gff=str(pred_file),
                    true_gff=str(true_gff),
                    fasta_path=str(fasta),
                    protein_fasta=str(run_dir / "proteins.faa"),
                    lineage=str(lineage),
                    out_dir=str(run_dir),
                    out_name="busco_run",
                    cpu=2,
                    busco_exe="busco",
                    output_gff_path=str(run_dir / "busco_colored_prediction.gff"),
                )
                display_name = _display_name_from_mapping(name_map, model_id, pred_file)
                reference_url = _lookup_reference_url(
                    reference_map, model_id, pred_file.stem, pred_file.name, display_name
                )
                busco_rows.append(
                    {
                        "model_id": model_id,
                        "reference_url": reference_url,
                        "complete": int(busco_result["Complete"]),
                        "fragmented": int(busco_result["Fragmented"]),
                        "missing": int(busco_result["Missing"]),
                        "colored_gff_url": f"/api/leaderboard/colored-gff/{model_id}",
                    }
                )
                self._set_state(
                    completed_models=idx,
                    busco_rows=sorted(
                        busco_rows,
                        key=lambda x: (x["complete"] + x["fragmented"], x["complete"]),
                        reverse=True,
                    ),
                )
            self._set_state(
                running=False,
                stage="Completed",
                current_model=None,
                message="Leaderboard is ready",
                finished_at=time.time(),
            )
        except Exception as exc:
            self._set_state(
                running=False,
                stage="Error",
                error=str(exc),
                message="Pipeline failed",
                finished_at=time.time(),
                current_model=None,
            )

    def _upload_worker(self) -> None:
        while True:
            job = self._upload_queue.get()
            sid = job.get("submission_id")
            try:
                with self._lock:
                    self._submission_jobs[sid]["status"] = "running"
                    self._submission_jobs[sid]["updated_at"] = time.time()
                    self._state.queue_current = job.get("model_name")
                    self._state.queue_length = self._upload_queue.qsize()
                true_gff = self.required_dir / "chr20.gff"
                fasta = self.required_dir / "Hs_NC_060944.1.fa"
                lineage = self.required_dir / "lineage" / "mammalia_odb10"
                with tempfile.TemporaryDirectory(
                    prefix="gene_leaderboard_submission_"
                ) as tmpdir:
                    tmp = Path(tmpdir)
                    pred = tmp / "prediction.gff"
                    pred.write_text(job.pop("gff_text"), encoding="utf-8")
                    raw = compute_gff_metric(
                        pred_gff=str(pred),
                        true_gff=str(true_gff),
                        stratifier="type",
                        types=["mRNA", "lnc_RNA"],
                        segments=["exon", "CDS"],
                    ).get("raw_result", {})
                    gene_row = {
                        "model_id": job["model_id"],
                        "temporary": True,
                        "lncrna_exon": int((raw.get("lnc_RNA") or [0, 0])[0]),
                        "mrna_exon": int((raw.get("mRNA") or [0, 0])[0]),
                        "mrna_cds": int((raw.get("mRNA") or [0, 0])[1]),
                    }
                    gene_row["total_score"] = (
                        gene_row["lncrna_exon"]
                        + gene_row["mrna_exon"]
                        + gene_row["mrna_cds"]
                    )
                    colored = tmp / "busco_colored_prediction.gff"
                    b = BUSCOEvaluator().busco_prepare_gff(
                        pred_gff=str(pred),
                        true_gff=str(true_gff),
                        fasta_path=str(fasta),
                        protein_fasta=str(tmp / "proteins.faa"),
                        lineage=str(lineage),
                        out_dir=str(tmp),
                        out_name="busco_run",
                        cpu=2,
                        busco_exe="busco",
                        output_gff_path=str(colored),
                    )
                    busco_row = {
                        "model_id": job["model_id"],
                        "temporary": True,
                        "complete": int(b["Complete"]),
                        "fragmented": int(b["Fragmented"]),
                        "missing": int(b["Missing"]),
                        "colored_gff_text": (
                            colored.read_text(encoding="utf-8")
                            if colored.exists()
                            else ""
                        ),
                    }
                with self._lock:
                    payload = {
                        "status": "completed",
                        "submission_id": sid,
                        "model_id": job["model_id"],
                        "model_name": job["model_name"],
                        "gene_row": gene_row,
                        "busco_row": busco_row,
                        "finished_at": time.time(),
                    }
                    self._submission_results[sid] = payload
                    self._submission_jobs[sid]["status"] = "completed"
                    self._submission_jobs[sid]["updated_at"] = time.time()
                    self._cleanup_expired_submissions()
            except Exception as exc:
                with self._lock:
                    self._submission_errors[sid] = {
                        "status": "failed",
                        "submission_id": sid,
                        "error": str(exc),
                        "finished_at": time.time(),
                    }
                    if sid in self._submission_jobs:
                        self._submission_jobs[sid]["status"] = "failed"
                        self._submission_jobs[sid]["updated_at"] = time.time()
                    self._state.message = f"Submission failed for {job.get('model_name', 'user submission')}: {exc}"
                    self._cleanup_expired_submissions()
            finally:
                with self._lock:
                    self._state.queue_current = None; self._state.queue_length = self._upload_queue.qsize()
                self._upload_queue.task_done()

    def get_colored_gff_path(self, model_id: str) -> Path:
        p = self.runs_dir / model_id / "busco_colored_prediction.gff"
        if not p.exists():
            raise FileNotFoundError(
                f"Colored GFF is not available for model: {model_id}"
            )
        return p

    def _sync_predictions_repo(
        self,
    ) -> tuple[list[Path], dict[str, str], dict[str, str]]:
        self.external_dir.mkdir(parents=True, exist_ok=True)
        if self.pred_repo_dir.exists():
            subprocess.run(
                ["git", "-C", str(self.pred_repo_dir), "pull", "--ff-only"], check=True
            )
        else:
            subprocess.run(
                ["git", "clone", PREDICTIONS_REPO_URL, str(self.pred_repo_dir)],
                check=True,
            )
        predictions_dir = self.pred_repo_dir / "predictions"
        mapping_file = self.pred_repo_dir / "name_mapping.json"
        reference_file_candidates = [
            self.pred_repo_dir / "reference.json",
            self.pred_repo_dir / "references.json",
        ]
        references_file = next((p for p in reference_file_candidates if p.exists()), None)
        if not predictions_dir.exists():
            raise FileNotFoundError("predictions folder is missing in predictions repo")
        name_map = (
            json.loads(mapping_file.read_text(encoding="utf-8"))
            if mapping_file.exists()
            else {}
        )
        raw_reference_map = (
            json.loads(references_file.read_text(encoding="utf-8"))
            if references_file is not None
            else {}
        )
        reference_map: dict[str, str] = {}
        for key, value in raw_reference_map.items():
            url = _extract_reference_url(value)
            if not url:
                continue

            for alias in _reference_aliases(key):
                reference_map[alias] = url

        prediction_files = sorted(predictions_dir.glob("*.gff"))
        model_name_map = {
            pred_file.stem: _display_name_from_mapping(name_map, pred_file.stem, pred_file)
            for pred_file in prediction_files
        }
        return (
            prediction_files,
            model_name_map,
            reference_map,
        )

    def _set_state(self, **kwargs: Any) -> None:
        with self._lock:
            for k, v in kwargs.items():
                setattr(self._state, k, v)
