"""
config.py — Central configuration for Hospital PACS System.
All environment-level settings live here.
"""

import os

# ─── Database ──────────────────────────────────────────────────────────────────
# SQLite — no external DB server required. The .db file is created automatically.
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DB_PATH      = os.path.join(BASE_DIR, "hospital_pacs.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# ─── JWT Authentication ─────────────────────────────────────────────────────────
SECRET_KEY                  = "HospitalPACS_SuperSecretKey_ChangeMeInProduction!"
ALGORITHM                   = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24   # 24 hours

# ─── Default Orthanc (used as fallback when no user-level credentials exist) ──
ORTHANC_URL      = "http://localhost:8042"
ORTHANC_USERNAME = "admin"
ORTHANC_PASSWORD = "password"

# ─── File Storage ──────────────────────────────────────────────────────────────
UPLOAD_ROOT_DIR    = "uploads"
DICOM_DIR          = "uploads/dicom"
PDF_DIR            = "uploads/pdf"
THUMBNAIL_DIR      = "uploads/thumbnails"

# ─── Role Definitions ──────────────────────────────────────────────────────────
ROLES = {
    1: "admin",
    2: "doctor",
    3: "lab_assistant",
    4: "patient",
    5: "radiologist",
}

# ─── RadiAnt DICOM Viewer (C-STORE SCU → RadiAnt SCP) ─────────────────────────
RADIANT_AE_TITLE = os.getenv("RADIANT_AE_TITLE", "RADIANT")
RADIANT_HOST     = os.getenv("RADIANT_HOST", "127.0.0.1")
RADIANT_PORT     = int(os.getenv("RADIANT_PORT", "11113"))

# ─── Our DICOM SCP Server (receives studies FROM RadiAnt / other DICOM clients)─
SCU_AE_TITLE     = os.getenv("SCU_AE_TITLE", "HOSPITAL_PACS")
SCP_AE_TITLE     = os.getenv("SCP_AE_TITLE", "HOSPITAL_PACS")
SCP_PORT         = int(os.getenv("SCP_PORT", "10402"))