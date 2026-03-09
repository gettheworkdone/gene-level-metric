from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.metric import (
    DEFAULT_ASS,
    DEFAULT_DSS,
    EXAMPLE_PAYLOADS,
    gene_level_metric,
)


class ComputeRequest(BaseModel):
    preds: list[list[int]]
    targets: list[list[int]]
    mapping: list[str]
    dna_sequences: str | list[str] | None = ""
    cds_heuristics: bool = False
    splice_filter: bool = False
    dss: list[str] = Field(default_factory=lambda: DEFAULT_DSS.copy())
    ass: list[str] = Field(default_factory=lambda: DEFAULT_ASS.copy())


ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"
ASSETS_DIR = STATIC_DIR / "assets"

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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/example")
def example() -> dict[str, Any]:
    return EXAMPLE_PAYLOADS


@app.post("/api/compute")
def compute(payload: ComputeRequest) -> dict[str, Any]:
    try:
        return gene_level_metric(
            preds=payload.preds,
            targets=payload.targets,
            mapping=payload.mapping,
            dna_sequences=payload.dna_sequences,
            cds_heuristics=payload.cds_heuristics,
            splice_filter=payload.splice_filter,
            dss=payload.dss,
            ass=payload.ass,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc


@app.get("/", response_model=None)
def root() -> Response:
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse(
        {
            "message": "Frontend build was not found. Build the frontend or run through Docker.",
            "health": "/api/health",
            "example": "/api/example",
            "compute": "/api/compute",
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
        {
            "message": "Frontend build was not found. Build the frontend or run through Docker.",
        },
        status_code=503,
    )
