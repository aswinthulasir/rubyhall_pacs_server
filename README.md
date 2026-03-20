# Hospital PACS System — Backend

A modular FastAPI + MySQL backend for a simple Hospital PACS (Picture Archiving and Communication System).

## Project Structure

```
hospital_pacs/
├── main.py                     # FastAPI app entry point
├── config.py                   # All settings (DB, JWT, Orthanc, paths)
├── database.py                 # SQLAlchemy engine + session + get_db()
├── models.py                   # ORM table definitions
├── schemas.py                  # Pydantic request/response models
├── create_db.py                # One-time DB setup + seed script
├── requirements.txt
├── FRONTEND_GUIDE.md           # Frontend build guide
│
├── auth/
│   ├── __init__.py
│   └── security.py             # bcrypt hashing + JWT + auth dependencies
│
├── routers/
│   ├── __init__.py
│   ├── auth_router.py          # /auth/register, /auth/login, /auth/me
│   ├── dicom_router.py         # /dicom/* — upload, confirm, list, thumbnail, download
│   ├── orthanc_router.py       # /orthanc/* — send, list, download, health
│   └── user_router.py          # /users/* — list, get, update
│
├── services/
│   ├── __init__.py
│   ├── dicom_service.py        # DICOM parsing, metadata extraction, thumbnail generation
│   └── orthanc_service.py      # Orthanc REST API wrapper
│
└── uploads/                    # Created automatically
    ├── dicom/
    ├── pdf/
    └── thumbnails/
```

---

## Prerequisites

- Python 3.10+
- MySQL 8.0+
- Orthanc running at `localhost:8042`

---

## Setup

### 1. Install Python dependencies

```bash
cd hospital_pacs
pip install -r requirements.txt
```

### 2. Set up the database

```bash
python create_db.py
```

This will:
- Create the `hospital_pacs` MySQL database
- Create all tables
- Seed the 5 roles (admin, doctor, lab_assistant, patient, radiologist)
- Create a default admin account: `admin` / `Admin@123`

### 3. Start the server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Open API docs

- Swagger UI: http://localhost:8000/docs
- ReDoc:       http://localhost:8000/redoc

---

## Default Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `Admin@123` |

Register more users via `POST /auth/register` with role_id:
- `1` = admin
- `2` = doctor
- `3` = lab_assistant
- `4` = patient
- `5` = radiologist

---

## Upload Flow

1. `POST /dicom/upload` — Upload DICOM file + MR Number → returns preview with extracted metadata and thumbnail
2. `POST /dicom/confirm/{id}` — Confirm and save the study permanently
3. After saving — optionally `POST /orthanc/send/{id}` to push to Orthanc

---

## Orthanc / RadiAnt

- Orthanc target: `http://localhost:8042` (credentials: admin / password)
- Send a study: `POST /orthanc/send/{study_id}`
- Browse Orthanc: `GET /orthanc/studies`
- Download for RadiAnt: `GET /dicom/download/{study_id}` — download the file and open in RadiAnt desktop viewer