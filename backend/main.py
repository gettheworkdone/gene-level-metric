from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import evaluate

from gene_level_core import DEFAULT_SEGMENTS, DEFAULT_TYPES, PYTHON_EXAMPLE

from .leaderboard_service import LeaderboardService


class PythonComputeRequest(BaseModel):
    preds: list[list[list[int]]]
    targets: list[list[list[int]]]
    mapping: list[str]
    stratifier: str = "type"
    types: list[str] = Field(default_factory=lambda: DEFAULT_TYPES.copy())
    segments: list[str] = Field(default_factory=lambda: DEFAULT_SEGMENTS.copy())


class GffComputeRequest(BaseModel):
    pred_gff_text: str
    true_gff_text: str
    stratifier: str = "type"
    types: list[str] = Field(default_factory=lambda: DEFAULT_TYPES.copy())
    segments: list[str] = Field(default_factory=lambda: DEFAULT_SEGMENTS.copy())


ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"
ASSETS_DIR = STATIC_DIR / "assets"
METRIC = evaluate.load(str(ROOT_DIR / "gene-level-metric.py"))
LEADERBOARD = LeaderboardService(ROOT_DIR)

app = FastAPI(title="GENATATOR Gene-level Metric", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.on_event("startup")
def start_leaderboard_pipeline() -> None:
    LEADERBOARD.start()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/example/python")
def python_example() -> dict[str, Any]:
    return PYTHON_EXAMPLE


@app.post("/api/compute/python")
def compute_python(payload: PythonComputeRequest) -> dict[str, Any]:
    try:
        return METRIC._run_gene_level_python_full(
            preds=payload.preds,
            targets=payload.targets,
            mapping=payload.mapping,
            stratifier=payload.stratifier,
            types=payload.types,
            segments=payload.segments,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc


@app.post("/api/compute/gff")
def compute_gff(payload: GffComputeRequest) -> dict[str, Any]:
    try:
        return METRIC._run_gene_level_gff_full(
            pred_gff=payload.pred_gff_text,
            true_gff=payload.true_gff_text,
            stratifier=payload.stratifier,
            types=payload.types,
            segments=payload.segments,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc




@app.get("/api/leaderboard/status")
def leaderboard_status() -> dict[str, Any]:
    return LEADERBOARD.status()


@app.post("/api/leaderboard/start")
def leaderboard_start() -> dict[str, Any]:
    return LEADERBOARD.start()


@app.get("/", response_model=None)
def root() -> Response:
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse(
        {
            "message": "Frontend build was not found. Build the frontend or run through Docker.",
            "health": "/api/health",
            "example": "/api/example/python",
            "compute_python": "/api/compute/python",
            "compute_gff": "/api/compute/gff",
        }
    )


@app.get("/{full_path:path}", response_model=None)
def spa_fallback(full_path: str) -> Response:
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found.")

    candidate = STATIC_DIR / full_path
    if candidate.exists() and candidate.is_file():
        return FileResponse(candidate)

    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    return JSONResponse(
        {"message": "Frontend build was not found. Build the frontend or run through Docker."},
        status_code=503,
    )
