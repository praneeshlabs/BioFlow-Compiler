"""
ProtocolForge FastAPI server.

Run with:  uvicorn app.server:app --reload --port 8000
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .golden_paths import list_golden_paths
from .orchestrator import compile_protocol
from .schemas import CompileRequest, GoldenPathPreview, ProtocolState

load_dotenv()

app = FastAPI(
    title="ProtocolForge API",
    description="Agentic Assay Compiler & Experimental Dependency Engine",
    version="1.0.0",
)

frontend_origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "service": "protocolforge-backend"}


@app.get("/api/golden-paths", response_model=list[GoldenPathPreview])
async def golden_paths() -> list[GoldenPathPreview]:
    """The three tuned example protocols the frontend offers as one-click
    demo loaders."""
    return [GoldenPathPreview(**p) for p in list_golden_paths()]


@app.post("/api/compile", response_model=ProtocolState)
async def compile_endpoint(payload: CompileRequest) -> ProtocolState:
    try:
        return await compile_protocol(payload.raw_text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Compilation failed: {exc}") from exc
