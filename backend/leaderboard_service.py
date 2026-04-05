from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue
from typing import Any

from gene_level_core import compute_gff_metric

from .busco_eval import BUSCOEvaluator

PREDICTIONS_REPO_URL = "https://github.com/alexeyshmelev/genatator-leaderboard-predictions.git"


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
    queue_length: int = 0
    queue_current: str | None = None

    def to_dict(self, user_gene_rows: list[dict[str, Any]], user_busco_rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "running": self.running,
            "stage": self.stage,
            "message": self.message,
            "total_models": self.total_models,
            "completed_models": self.completed_models,
            "current_model": self.current_model,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "launch_date": self.launch_date,
            "gene_rows": self.gene_rows,
            "busco_rows": self.busco_rows,
            "model_name_map": self.model_name_map,
            "queue_length": self.queue_length,
            "queue_current": self.queue_current,
            "user_gene_rows": user_gene_rows,
            "user_busco_rows": user_busco_rows,
        }


class LeaderboardService:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.external_dir = root_dir / "external"
        self.pred_repo_dir = self.external_dir / "genatator-leaderboard-predictions"
        self.required_dir = root_dir / "leaderboard_required_files"
        self.runs_dir = root_dir / "leaderboard_runs"
        self.upload_dir = root_dir / "leaderboard_uploads"
        self._lock = threading.Lock()
        self._state = LeaderboardState()
        self._user_gene_rows: list[dict[str, Any]] = []
        self._user_busco_rows: list[dict[str, Any]] = []
        self._upload_queue: Queue[dict[str, Any]] = Queue()
        threading.Thread(target=self._upload_worker, daemon=True).start()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self._state.to_dict(self._user_gene_rows, self._user_busco_rows)

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._state.running:
                return self._state.to_dict(self._user_gene_rows, self._user_busco_rows)
            self._state = LeaderboardState(running=True, stage="Building leaderboard", message="Building leaderboard...", started_at=time.time())

        thread = threading.Thread(target=self._run_pipeline, daemon=True)
        thread.start()
        return self.status()

    def enqueue_submission(self, model_name: str, gff_text: str) -> dict[str, Any]:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        sub_id = str(uuid.uuid4())
        gff_path = self.upload_dir / f"{sub_id}.gff"
        gff_path.write_text(gff_text, encoding="utf-8")
        job = {"id": sub_id, "model_name": model_name.strip() or f"user-{sub_id[:8]}", "gff_path": gff_path}
        self._upload_queue.put(job)
        with self._lock:
            self._state.queue_length = self._upload_queue.qsize()
            position = self._state.queue_length
        return {"submission_id": sub_id, "position": position}

    def _run_pipeline(self) -> None:
        try:
            self.required_dir.mkdir(parents=True, exist_ok=True)
            self.runs_dir.mkdir(parents=True, exist_ok=True)
            true_gff = self.required_dir / "chr20.gff"
            fasta = self.required_dir / "Hs_NC_060944.1.fa"
            lineage = self.required_dir / "lineage" / "mammalia_odb10"
            if not true_gff.exists() or not fasta.exists() or not lineage.exists():
                raise FileNotFoundError("Missing required files. Put chr20.gff, Hs_NC_060944.1.fa and lineage/mammalia_odb10 into leaderboard_required_files/.")

            self._set_state(stage="Syncing repository", message="Syncing predictions repository")
            prediction_files, name_map = self._sync_predictions_repo()
            self._set_state(total_models=len(prediction_files), model_name_map=name_map)

            busco = BUSCOEvaluator()
            gene_rows: list[dict[str, Any]] = []
            busco_rows: list[dict[str, Any]] = []

            for idx, pred_file in enumerate(prediction_files, start=1):
                model_id = pred_file.stem
                self._set_state(stage="Gene-level metric calculation", current_model=model_id, message=f"Gene-level metric calculation {idx}/{len(prediction_files)}")
                gene_result = compute_gff_metric(pred_gff=str(pred_file), true_gff=str(true_gff), stratifier="type", types=["mRNA", "lnc_RNA"], segments=["exon", "CDS"])
                raw = gene_result.get("raw_result", {})
                gene_row = {
                    "model_id": model_id,
                    "lncrna_exon": int((raw.get("lnc_RNA") or [0, 0])[0]),
                    "mrna_exon": int((raw.get("mRNA") or [0, 0])[0]),
                    "mrna_cds": int((raw.get("mRNA") or [0, 0])[1]),
                }
                gene_row["total_score"] = gene_row["lncrna_exon"] + gene_row["mrna_exon"] + gene_row["mrna_cds"]
                gene_rows.append(gene_row)
                self._set_state(completed_models=idx, gene_rows=sorted(gene_rows, key=lambda x: x["total_score"], reverse=True))

            for idx, pred_file in enumerate(prediction_files, start=1):
                model_id = pred_file.stem
                self._set_state(stage="BUSCO metric calculation", current_model=model_id, message=f"BUSCO metric calculation {idx}/{len(prediction_files)}")
                run_dir = self.runs_dir / model_id
                if run_dir.exists():
                    shutil.rmtree(run_dir)
                run_dir.mkdir(parents=True, exist_ok=True)
                colored_gff_path = run_dir / "busco_colored_prediction.gff"
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
                    output_gff_path=str(colored_gff_path),
                )
                busco_rows.append({
                    "model_id": model_id,
                    "complete": int(busco_result["Complete"]),
                    "fragmented": int(busco_result["Fragmented"]),
                    "missing": int(busco_result["Missing"]),
                    "colored_gff_url": f"/api/leaderboard/colored-gff/{model_id}",
                })
                self._set_state(completed_models=idx, busco_rows=sorted(busco_rows, key=lambda x: (x["complete"] + x["fragmented"], x["complete"]), reverse=True))

            self._set_state(running=False, stage="Completed", current_model=None, message="Leaderboard is ready", finished_at=time.time())
        except Exception as exc:
            self._set_state(running=False, stage="Error", error=str(exc), message="Pipeline failed", finished_at=time.time(), current_model=None)

    def get_colored_gff_path(self, model_id: str) -> Path:
        p = self.runs_dir / model_id / "busco_colored_prediction.gff"
        if not p.exists():
            raise FileNotFoundError(f"Colored GFF is not available for model: {model_id}")
        return p

    def _sync_predictions_repo(self) -> tuple[list[Path], dict[str, str]]:
        self.external_dir.mkdir(parents=True, exist_ok=True)
        if self.pred_repo_dir.exists():
            subprocess.run(["git", "-C", str(self.pred_repo_dir), "pull", "--ff-only"], check=True)
        else:
            subprocess.run(["git", "clone", PREDICTIONS_REPO_URL, str(self.pred_repo_dir)], check=True)

        predictions_dir = self.pred_repo_dir / "predictions"
        mapping_file = self.pred_repo_dir / "name_mapping.json"
        if not predictions_dir.exists():
            raise FileNotFoundError("predictions folder is missing in predictions repo")
        name_map: dict[str, str] = {}
        if mapping_file.exists():
            name_map = json.loads(mapping_file.read_text(encoding="utf-8"))
        normalized_map = {Path(k).stem: v for k, v in name_map.items()}
        return sorted(predictions_dir.glob("*.gff")), normalized_map

    def _upload_worker(self) -> None:
        while True:
            job = self._upload_queue.get()
            try:
                with self._lock:
                    self._state.queue_current = job["model_name"]
                    self._state.queue_length = self._upload_queue.qsize()
                true_gff = self.required_dir / "chr20.gff"
                fasta = self.required_dir / "Hs_NC_060944.1.fa"
                lineage = self.required_dir / "lineage" / "mammalia_odb10"
                busco = BUSCOEvaluator()
                gene_result = compute_gff_metric(pred_gff=str(job["gff_path"]), true_gff=str(true_gff), stratifier="type", types=["mRNA", "lnc_RNA"], segments=["exon", "CDS"])
                raw = gene_result.get("raw_result", {})
                gene_row = {
                    "model_id": job["model_name"],
                    "lncrna_exon": int((raw.get("lnc_RNA") or [0, 0])[0]),
                    "mrna_exon": int((raw.get("mRNA") or [0, 0])[0]),
                    "mrna_cds": int((raw.get("mRNA") or [0, 0])[1]),
                }
                gene_row["total_score"] = gene_row["lncrna_exon"] + gene_row["mrna_exon"] + gene_row["mrna_cds"]

                run_dir = self.runs_dir / f"user_{job['id']}"
                if run_dir.exists():
                    shutil.rmtree(run_dir)
                run_dir.mkdir(parents=True, exist_ok=True)
                colored_gff_path = run_dir / "busco_colored_prediction.gff"
                busco_result = busco.busco_prepare_gff(pred_gff=str(job["gff_path"]), true_gff=str(true_gff), fasta_path=str(fasta), protein_fasta=str(run_dir / "proteins.faa"), lineage=str(lineage), out_dir=str(run_dir), out_name="busco_run", cpu=2, busco_exe="busco", output_gff_path=str(colored_gff_path))
                busco_row = {
                    "model_id": job["model_name"],
                    "complete": int(busco_result["Complete"]),
                    "fragmented": int(busco_result["Fragmented"]),
                    "missing": int(busco_result["Missing"]),
                    "colored_gff_url": f"/api/leaderboard/user-colored-gff/{job['id']}",
                }
                with self._lock:
                    self._user_gene_rows = [r for r in self._user_gene_rows if r["model_id"] != job["model_name"]] + [gene_row]
                    self._user_busco_rows = [r for r in self._user_busco_rows if r["model_id"] != job["model_name"]] + [busco_row]
            finally:
                with self._lock:
                    self._state.queue_current = None
                    self._state.queue_length = self._upload_queue.qsize()
                self._upload_queue.task_done()

    def get_user_colored_gff_path(self, submission_id: str) -> Path:
        p = self.runs_dir / f"user_{submission_id}" / "busco_colored_prediction.gff"
        if not p.exists():
            raise FileNotFoundError("Colored GFF for user submission not found")
        return p

    def _set_state(self, **kwargs: Any) -> None:
        with self._lock:
            for key, value in kwargs.items():
                setattr(self._state, key, value)
