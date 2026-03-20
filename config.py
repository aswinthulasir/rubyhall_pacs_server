"""
config.py — Central configuration for Hospital PACS System.
All environment-level settings live here.
"""

from urllib.parse import quote_plus


# ─── Database ──────────────────────────────────────────────────────────────────
DB_USER     = "root"
DB_PASSWORD = quote_plus("Aswin2000")   # URL-safe encoding
DB_HOST     = "localhost"
DB_PORT     = 3306
DB_NAME     = "hospital_pacs"

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ─── JWT Authentication ─────────────────────────────────────────────────────────
SECRET_KEY                  = "HospitalPACS_SuperSecretKey_ChangeMeInProduction!"
ALGORITHM                   = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24   # 24 hours

# ─── Orthanc ───────────────────────────────────────────────────────────────────
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