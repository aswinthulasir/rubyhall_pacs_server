"""
main.py — FastAPI application entry point for the Hospital PACS System.

Start the server with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Interactive API docs:
    http://localhost:8000/docs    (Swagger UI)
    http://localhost:8000/redoc   (ReDoc)
"""

import os
import logging

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import config
from routers.auth_router import router as auth_router
from routers.dicom_router import router as dicom_router
from routers.orthanc_router import router as orthanc_router
from routers.user_router import router as user_router

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pacs")

# ─── Ensure upload directories exist on startup ────────────────────────────────
for _dir in (config.DICOM_DIR, config.PDF_DIR, config.THUMBNAIL_DIR):
    os.makedirs(_dir, exist_ok=True)

# ─── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "Hospital PACS System",
    description = (
        "A simple PACS backend for uploading, storing, and routing DICOM studies. "
        "Supports Orthanc integration and RadiAnt viewer compatibility."
    ),
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# ─── CORS (adjust origins for your frontend domain in production) ──────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],   # Replace with specific origins in production
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ─── Serve static upload files (thumbnails, DICOMs, PDFs) ─────────────────────
app.mount(
    "/static/uploads",
    StaticFiles(directory=config.UPLOAD_ROOT_DIR),
    name="uploads",
)

# ─── Serve Frontend static assets (CSS / JS) ──────────────────────────────────
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
app.mount(
    "/frontend",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="frontend",
)

# ─── Register routers ─────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(dicom_router)
app.include_router(orthanc_router)
app.include_router(user_router)


# ─── Serve frontend index.html at root ─────────────────────────────────────────
@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/health", tags=["Health"])
def health_check():
    """Simple liveness probe."""
    return {"status": "ok"}


# ─── Startup event ─────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    logger.info("Hospital PACS Server started.")
    logger.info("Orthanc target: %s", config.ORTHANC_URL)
    logger.info("Upload directory: %s", config.UPLOAD_ROOT_DIR)