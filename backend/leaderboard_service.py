from __future__ import annotations

import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
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
    gene_rows: list[dict[str, Any]] = field(default_factory=list)
    busco_rows: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
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
            "gene_rows": self.gene_rows,
            "busco_rows": self.busco_rows,
        }


class LeaderboardService:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.external_dir = root_dir / "external"
        self.pred_repo_dir = self.external_dir / "genatator-leaderboard-predictions"
        self.required_dir = root_dir / "leaderboard_required_files"
        self.runs_dir = root_dir / "leaderboard_runs"
        self._lock = threading.Lock()
        self._state = LeaderboardState()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self._state.to_dict()

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._state.running:
                return self._state.to_dict()
            self._state = LeaderboardState(running=True, stage="initializing", message="Starting leaderboard pipeline", started_at=time.time())

        thread = threading.Thread(target=self._run_pipeline, daemon=True)
        thread.start()
        return self.status()

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

            self._set_state(stage="sync", message="Syncing predictions repository")
            prediction_files = self._sync_predictions_repo()
            self._set_state(total_models=len(prediction_files), message=f"Found {len(prediction_files)} .gff files")

            busco = BUSCOEvaluator()
            gene_rows: list[dict[str, Any]] = []
            busco_rows: list[dict[str, Any]] = []

            for idx, pred_file in enumerate(prediction_files, start=1):
                model_id = pred_file.stem
                self._set_state(stage="gene", current_model=model_id, message=f"[gene {idx}/{len(prediction_files)}] Gene-level metric")
                gene_result = compute_gff_metric(
                    pred_gff=str(pred_file),
                    true_gff=str(true_gff),
                    stratifier="type",
                    types=["mRNA", "lnc_RNA"],
                    segments=["exon", "CDS"],
                )
                raw = gene_result.get("raw_result", {})
                gene_row = {
                    "model_id": model_id,
                    "lncrna_exon": int((raw.get("lnc_RNA") or [0, 0])[0]),
                    "mrna_exon": int((raw.get("mRNA") or [0, 0])[0]),
                    "mrna_cds": int((raw.get("mRNA") or [0, 0])[1]),
                }
                gene_row["score_gene"] = gene_row["lncrna_exon"] + max(gene_row["mrna_exon"], gene_row["mrna_cds"])
                gene_rows.append(gene_row)
                self._set_state(
                    completed_models=idx,
                    gene_rows=sorted(gene_rows, key=lambda x: x["score_gene"], reverse=True),
                )

            for idx, pred_file in enumerate(prediction_files, start=1):
                model_id = pred_file.stem
                self._set_state(stage="busco", current_model=model_id, message=f"[busco {idx}/{len(prediction_files)}] BUSCO metric")
                run_dir = self.runs_dir / model_id
                if run_dir.exists():
                    shutil.rmtree(run_dir)
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
                )
                busco_rows.append(
                    {
                        "model_id": model_id,
                        "complete": int(busco_result["Complete"]),
                        "fragmented": int(busco_result["Fragmented"]),
                        "missing": int(busco_result["Missing"]),
                    }
                )
                self._set_state(
                    completed_models=idx,
                    busco_rows=sorted(busco_rows, key=lambda x: (x["complete"] + x["fragmented"], x["complete"]), reverse=True),
                )

            self._set_state(running=False, stage="done", current_model=None, message="Leaderboard is ready", finished_at=time.time())
        except Exception as exc:
            self._set_state(running=False, stage="error", error=str(exc), message="Pipeline failed", finished_at=time.time(), current_model=None)

    def _sync_predictions_repo(self) -> list[Path]:
        self.external_dir.mkdir(parents=True, exist_ok=True)
        if self.pred_repo_dir.exists():
            subprocess.run(["git", "-C", str(self.pred_repo_dir), "pull", "--ff-only"], check=True)
        else:
            subprocess.run(["git", "clone", PREDICTIONS_REPO_URL, str(self.pred_repo_dir)], check=True)

        predictions_dir = self.pred_repo_dir / "predictions"
        if not predictions_dir.exists():
            raise FileNotFoundError("predictions folder is missing in predictions repo")
        return sorted(predictions_dir.glob("*.gff"))

    def _set_state(self, **kwargs: Any) -> None:
        with self._lock:
            for key, value in kwargs.items():
                setattr(self._state, key, value)
