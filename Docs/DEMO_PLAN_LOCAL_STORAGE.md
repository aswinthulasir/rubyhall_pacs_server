# Ruby Hall Demo — Local Storage Architecture & Implementation Plan

**Created:** March 20, 2026
**Status:** Planning — Local Storage Variant
**Goal:** A standalone web platform where patients/doctors upload DICOM studies, the hospital reviews and reports on them, and reports flow back to the original uploader — with full data isolation, optional encryption, and two deployment modes (local demo + production).

> **This plan replaces the SPIN/named-PACS-server variant.** All DICOM storage, encryption, and finalization is handled directly by the Demo App. SPIN, pynetdicom SCU, Orthanc forwarding, and brix DB are not required.

---

## 1. The Full Workflow — What We're Building

The Demo App **is** the storage backend. It receives uploads over HTTP, saves `.dcm` files to disk (with optional AES encryption), registers studies in its own database, and serves images/reports back to the browser — no separate DICOM server required.

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                    RUBY HALL HOSPITAL LAN                        │
  │                                                                  │
  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌─────────────┐    │
  │  │ CT       │   │ MR       │   │ X-Ray    │   │ Doctor's    │    │
  │  │ Scanner  │   │ Scanner  │   │ Machine  │   │ Workstation │    │
  │  └──────────┘   └──────────┘   └──────────┘   └──────────── ┘    │
  │                                                                  │
  │              ┌─────────────────────────────────────┐             │
  │              │ Demo App (FastAPI)                  │             │
  │              │ :8080                               │◀─── INTERNET │
  │              │ • HTTP upload (browser / modality)  │             │
  │              │ • Direct disk save + AES optional   │             │
  │              │ • DB registration (demo DB)         │             │
  │              │ • Report upload endpoint            │             │
  │              │ • Image/report serve                │             │
  │              └────────────────┬────────────────────┘             │
  │                               │                                  │
  │              ┌────────────────┴─────────────────┐                │
  │              │ Local Storage                    │                │
  │              │ D:\demoData\dcm\<email>\<uid>\   │                │
  │              │  ├── 000/00001.dcm  (CT image)   │                │
  │              │  ├── 001/00001.dcm  (SR report)  │                │
  │              │  ├── report.pdf                  │                │
  │              │  └── thumbnail.jpg               │                │
  │              └──────────────────────────────────┘                │
  └──────────────────────────────────────────────────────────────────┘

  THE COMPLETE CYCLE:

  ┌──────────────┐                       ┌──────────────────────────────────┐
  │ PATIENT/     │  1. Upload CT         │    RUBY HALL / YOUR PC           │
  │ REFERRING    │     via browser       │                                   │
  │ DOCTOR       │──────────────────────▶│  Demo App (FastAPI :8080)        │
  │ (at home,    │                       │       │                           │
  │  over        │                       │       │ 2. Save .dcm to disk     │
  │  internet)   │                       │       │    Register in Demo DB   │
  │              │                       │       ▼                           │
  │              │                       │  Local Storage + Demo DB         │
  │              │                       │       │                           │
  │              │                       │       │ 3. Doctor logs in,       │
  │              │                       │       │    reviews images        │
  │              │                       │       │                           │
  │              │                       │       │ 4. Doctor uploads PDF    │
  │              │                       │       │    or SR report via      │
  │              │                       │       │    browser/API           │
  │              │                       │       │                           │
  │              │                       │       │ 5. Demo DB marks         │
  │              │                       │       │    has_report = true     │
  │              │  6. View report       │       ▼                           │
  │              │◀─────────────────────│  Patient dashboard updated        │
  │              │     on dashboard      │                                   │
  └──────────────┘                       └──────────────────────────────────┘
```

### Step-by-Step:

| Step | Who | Where | What Happens | How |
|------|-----|-------|-------------|-----|
| **1a** | Patient (remote) | Internet → browser | Uploads .dcm files via drag-and-drop | HTTP POST → Demo API → `local_storage.py` → disk |
| **1b** | Doctor/technician | Browser | Uploads modality files directly | Same HTTP POST endpoint |
| **2** | Demo App | Server | Saves to disk, registers in Demo DB | `save_dicom_files()` → INSERT into studies/instances |
| **3** | Doctor | Browser | Logs into demo, views images in Cornerstone.js viewer | GET /api/viewer endpoints serve decrypted images |
| **4** | Doctor | Browser | Uploads PDF or SR report file | POST /api/studies/:id/report (multipart) |
| **5** | Demo App | Server | Saves report file, sets `has_report=true` | Direct DB UPDATE, no re-finalization needed |
| **6** | Patient (remote) | Internet → browser | Sees "Report Available" badge, views report | GET /api/viewer/:id/report → serve PDF/SR |

---

## 2. System Architecture — Local Storage Production

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    RUBY HALL HOSPITAL (Physical Server)              │
  │                                                                      │
  │  INTERNET ──▶ Caddy :443 ──┬── /       → Demo FastAPI :8080        │
  │  (patients,   (TLS auto)   ├── /api/*  → Demo FastAPI :8080        │
  │   referring                 ├── /static → Demo FastAPI :8080        │
  │   doctors)                  └── blocked: everything else            │
  │                                                                      │
  │  ┌─────────────────────────────────────────────────────────────────┐ │
  │  │                                                                 │ │
  │  │  ┌──────────────────┐   ┌──────────────────────────────────┐   │ │
  │  │  │ Demo FastAPI     │   │ Local Storage                    │   │ │
  │  │  │ :8080            │   │ D:\demoData\dcm\                 │   │ │
  │  │  │ • Web pages      │   │ └── owner@email.com/             │   │ │
  │  │  │ • REST API       │   │     └── <random_uid>/            │   │ │
  │  │  │ • Upload handler │──▶│         ├── 000/00001.dcm        │   │ │
  │  │  │   (direct save)  │   │         ├── 001/00001.dcm        │   │ │
  │  │  │ • Report upload  │   │         ├── report.pdf           │   │ │
  │  │  │ • Image serve    │   │         └── thumbnail.jpg        │   │ │
  │  │  └────────┬─────────┘   └──────────────────────────────────┘   │ │
  │  │           │                                                     │ │
  │  │  ┌────────┴─────────────────────────────────────────────────┐  │ │
  │  │  │ Demo DB :5432 (PostgreSQL)                                │  │ │
  │  │  │ users, studies, instances, refresh_tokens, web_uploads    │  │ │
  │  │  └──────────────────────────────────────────────────────────┘  │ │
  │  │                                                                 │ │
  │  └─────────────────────────────────────────────────────────────────┘ │
  └──────────────────────────────────────────────────────────────────────┘

  NETWORK ACCESS:
  ┌─────────────────┬──────────────────────────────────────────┐
  │ Port            │ Who can reach it                          │
  ├─────────────────┼──────────────────────────────────────────┤
  │ :443  (Caddy)   │ Internet (patients, referring doctors)   │
  │ :8080 (Demo)    │ localhost only (behind Caddy)            │
  │ :5432 (Demo DB) │ localhost only                           │
  └─────────────────┴──────────────────────────────────────────┘
```

---

## 3. Upload — Direct File Save (No DICOM Bridge)

The original plan used a pynetdicom SCU bridge to forward uploads to SPIN via C-STORE. Without SPIN, the Demo App saves files directly.

### How It Works

```
  Browser ──HTTP POST (multipart)──▶ Demo API ──save──▶ disk
                                          │
                                          └──▶ INSERT into Demo DB
```

### `local_storage.py`

```python
# demo/api/upload/local_storage.py
import os, uuid, json, gzip
from pathlib import Path
from io import BytesIO
from datetime import datetime
import pydicom
from PIL import Image
import numpy as np

STORAGE_DIR = Path(os.getenv('LOCAL_DATA_DIR', 'D:/demoData/dcm'))

def save_dicom_files(file_bytes_list: list[bytes], owner_email: str) -> dict:
    """
    Save a batch of DICOM files to disk and return study metadata.
    All files in one call must belong to the same study.
    """
    study_uid = None
    random_uid = str(uuid.uuid4()).replace("-", "")
    study_dir = None
    series_map = {}       # SeriesInstanceUID → series_index
    thumbnail_path = None

    instances = []

    for file_bytes in file_bytes_list:
        try:
            ds = pydicom.dcmread(BytesIO(file_bytes))
        except Exception as e:
            continue  # Skip unreadable files

        study_uid = study_uid or ds.StudyInstanceUID
        series_uid = getattr(ds, 'SeriesInstanceUID', 'unknown')

        if study_dir is None:
            study_dir = STORAGE_DIR / owner_email / random_uid
            study_dir.mkdir(parents=True, exist_ok=True)

        if series_uid not in series_map:
            series_map[series_uid] = len(series_map)
        series_idx = series_map[series_uid]
        series_folder = f"{series_idx:03d}"

        series_dir = study_dir / series_folder
        series_dir.mkdir(exist_ok=True)

        instance_num = getattr(ds, 'InstanceNumber', len(instances) + 1)
        filename = f"{instance_num:05d}.dcm"
        out_path = series_dir / filename

        # Detect instance type
        sop = getattr(ds, 'SOPClassUID', '')
        if sop.startswith('1.2.840.10008.5.1.4.1.1.88.'):
            instance_type = 'SR'
        elif sop == '1.2.840.10008.5.1.4.1.1.104.1':
            instance_type = 'NON_PIXEL'  # Encapsulated PDF
        elif hasattr(ds, 'PixelData'):
            instance_type = 'IMAGE'
        else:
            instance_type = 'NON_PIXEL'

        # Optionally encrypt here — see Section 3a
        out_path.write_bytes(file_bytes)

        instances.append({
            'series_folder': series_folder,
            'instance_file': filename,
            'sop_class_uid': str(sop),
            'instance_type': instance_type,
            'instance_number': int(instance_num),
            'is_report': instance_type in ('SR', 'NON_PIXEL'),
        })

        # Generate thumbnail from first IMAGE instance
        if instance_type == 'IMAGE' and thumbnail_path is None:
            thumbnail_path = _generate_thumbnail(ds, study_dir)

    # Write StudyInfo.json alongside the files
    if study_dir:
        study_info = {
            'study_uid': study_uid,
            'random_uid': random_uid,
            'owner_email': owner_email,
            'instances': instances,
        }
        (study_dir / 'StudyInfo.json').write_text(
            json.dumps(study_info, indent=2))

    return {
        'study_uid': study_uid,
        'random_uid': random_uid,
        'study_dir': str(study_dir),
        'instances': instances,
        'thumbnail_path': str(thumbnail_path) if thumbnail_path else None,
        'series_count': len(series_map),
        'instance_count': len(instances),
        'image_count': sum(1 for i in instances if i['instance_type'] == 'IMAGE'),
        'sr_count': sum(1 for i in instances if i['instance_type'] == 'SR'),
        'pdf_count': sum(1 for i in instances
                        if i['sop_class_uid'] == '1.2.840.10008.5.1.4.1.1.104.1'),
    }


def _generate_thumbnail(ds, study_dir: Path) -> Path:
    """Render first slice to a 256x256 JPEG thumbnail."""
    try:
        arr = ds.pixel_array.astype(float)
        # Windowing
        wc = float(getattr(ds, 'WindowCenter', arr.mean()))
        ww = float(getattr(ds, 'WindowWidth', arr.std() * 4 or 400))
        lo, hi = wc - ww / 2, wc + ww / 2
        arr = np.clip((arr - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr).convert('L').resize((256, 256))
        thumb_path = study_dir / 'thumbnail.jpg'
        img.save(thumb_path, 'JPEG', quality=70)
        return thumb_path
    except Exception:
        return None
```

### Upload Route

```python
# demo/api/upload/routes.py
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from typing import List
from ..dependencies import get_current_user, get_db
from .local_storage import save_dicom_files

router = APIRouter(prefix="/api/upload")

@router.post("")
async def upload_dicom(
    files: List[UploadFile] = File(...),
    user=Depends(get_current_user),
    db=Depends(get_db)
):
    if not files:
        raise HTTPException(400, "No files provided")

    file_bytes_list = [await f.read() for f in files]

    # Save to disk
    result = save_dicom_files(file_bytes_list, user['email'])
    if not result['study_uid']:
        raise HTTPException(422, "No valid DICOM files found")

    # Get patient metadata from first instance
    import pydicom
    from io import BytesIO
    ds = pydicom.dcmread(BytesIO(file_bytes_list[0]))
    patient_name = str(getattr(ds, 'PatientName', '') or '')
    patient_id = str(getattr(ds, 'PatientID', '') or '')
    study_date_raw = str(getattr(ds, 'StudyDate', '') or '')
    modality = str(getattr(ds, 'Modality', '') or '')
    description = str(getattr(ds, 'StudyDescription', '') or '')

    # Parse YYYYMMDD
    study_date = None
    if len(study_date_raw) == 8:
        from datetime import date
        study_date = date(int(study_date_raw[:4]),
                         int(study_date_raw[4:6]),
                         int(study_date_raw[6:]))

    has_report = result['sr_count'] > 0 or result['pdf_count'] > 0

    # Register in Demo DB
    study = await db.fetchrow("""
        INSERT INTO studies (
            study_uid, random_uid, owner_email,
            patient_name, patient_id, study_date, modality,
            description, instance_count, image_count,
            sr_count, pdf_count, series_count,
            study_dir, thumbnail_path,
            has_report, status, source
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
        ON CONFLICT (study_uid) DO UPDATE SET
            instance_count = EXCLUDED.instance_count,
            image_count = EXCLUDED.image_count,
            has_report = studies.has_report OR EXCLUDED.has_report,
            status = CASE WHEN EXCLUDED.has_report THEN 'reported'
                          ELSE 'ready' END,
            updated_at = NOW()
        RETURNING id
    """,
        result['study_uid'], result['random_uid'], user['email'],
        patient_name, patient_id, study_date, modality,
        description, result['instance_count'], result['image_count'],
        result['sr_count'], result['pdf_count'], result['series_count'],
        result['study_dir'], result['thumbnail_path'],
        has_report, 'reported' if has_report else 'ready', 'web'
    )
    study_id = study['id']

    # Register instances
    for inst in result['instances']:
        await db.execute("""
            INSERT INTO instances (
                study_id, series_folder, instance_file,
                sop_class_uid, instance_type, instance_number, is_report
            ) VALUES ($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT (study_id, series_folder, instance_file) DO NOTHING
        """,
            study_id, inst['series_folder'], inst['instance_file'],
            inst['sop_class_uid'], inst['instance_type'],
            inst['instance_number'], inst['is_report']
        )

    return {
        "status": "ok",
        "study_uid": result['study_uid'],
        "instance_count": result['instance_count'],
        "has_report": has_report,
    }
```

---

### 3a. Optional: Own AES Encryption Layer

If you want at-rest encryption without SPIN, add this wrapper. Keys are stored in the Demo DB instead of brix.

```python
# demo/api/upload/crypto.py
import os, secrets
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

KEY_SIZE = 32   # AES-256

def generate_key() -> bytes:
    return secrets.token_bytes(KEY_SIZE)

def encrypt(data: bytes, key: bytes) -> bytes:
    """AES-256-CTR: prepend 16-byte nonce."""
    nonce = secrets.token_bytes(16)
    cipher = Cipher(algorithms.AES(key), modes.CTR(nonce))
    enc = cipher.encryptor()
    return nonce + enc.update(data) + enc.finalize()

def decrypt(data: bytes, key: bytes) -> bytes:
    nonce, ciphertext = data[:16], data[16:]
    cipher = Cipher(algorithms.AES(key), modes.CTR(nonce))
    dec = cipher.decryptor()
    return dec.update(ciphertext) + dec.finalize()
```

To enable:

1. Add `aes_key BYTEA` column to the `studies` table.
2. In `save_dicom_files()`, call `encrypt(file_bytes, key)` before `out_path.write_bytes(...)`.
3. In `decrypt_helper.py`, call `decrypt(raw, key)` before parsing.
4. Store the key: `UPDATE studies SET aes_key = $1 WHERE study_uid = $2`

Set `ENCRYPT_AT_REST=true` in `.env` to toggle. The rest of the app is unchanged.

---

## 4. The Report-Back Workflow

Without SPIN re-finalization, report upload is a simple multipart POST. Doctors log in and submit a PDF or DICOM SR file through the admin/doctor interface.

### Report Upload Endpoint

```python
# demo/api/studies/routes.py  (add to existing router)

@router.post("/{study_id}/report")
async def upload_report(
    study_id: int,
    file: UploadFile = File(...),
    user=Depends(require_doctor_or_admin),
    db=Depends(get_db)
):
    study = await db.fetchrow(
        "SELECT * FROM studies WHERE id = $1 AND is_deleted = false",
        study_id)
    if not study:
        raise HTTPException(404)

    data = await file.read()
    study_dir = Path(study['study_dir'])

    # Determine file extension
    filename = file.filename or "report"
    ext = Path(filename).suffix.lower() or '.pdf'
    out_path = study_dir / f"report{ext}"
    out_path.write_bytes(data)

    # Mark report available in DB
    await db.execute("""
        UPDATE studies
        SET has_report = true,
            report_ready_at = NOW(),
            status = 'reported',
            updated_at = NOW()
        WHERE id = $1
    """, study_id)

    return {"status": "ok", "report_path": str(out_path)}
```

### Report Serve Endpoint

```python
@router.get("/{study_id}/report")
async def get_report(
    study_id: int,
    user=Depends(get_current_user),
    db=Depends(get_db)
):
    study = await db.fetchrow("""
        SELECT s.* FROM studies s
        LEFT JOIN study_assignments sa ON sa.study_id = s.id
        WHERE s.id = $1
          AND s.is_deleted = false
          AND (s.owner_email = $2 OR sa.assigned_to = $2)
    """, study_id, user['email'])
    if not study:
        raise HTTPException(404)

    study_dir = Path(study['study_dir'])

    # Look for report.pdf or report.dcm
    for ext in ['.pdf', '.dcm', '.sr']:
        rp = study_dir / f"report{ext}"
        if rp.exists():
            media = 'application/pdf' if ext == '.pdf' else 'application/dicom'
            return FileResponse(str(rp), media_type=media)

    raise HTTPException(404, "No report found")
```

---

## 5. Image Serve — Decrypt Helper (Simplified)

Without SPIN encryption, images are plain `.dcm` files. The viewer serves them directly, or decodes pixel data to JPEG for the browser.

```python
# demo/api/viewer/decrypt_helper.py
import pydicom
import numpy as np
from PIL import Image
from io import BytesIO
import json, pickle, gzip

ENCRYPT_AT_REST = os.getenv('ENCRYPT_AT_REST', 'false').lower() == 'true'

def read_file(path: str, aes_key: bytes | None = None) -> bytes:
    """Read raw file bytes, decrypting if at-rest encryption is enabled."""
    raw = Path(path).read_bytes()
    if ENCRYPT_AT_REST and aes_key:
        from .crypto import decrypt
        return decrypt(raw, aes_key)
    return raw


def serve_instance(path: str, instance_type: str,
                   aes_key: bytes | None = None) -> tuple[str, bytes]:
    """
    Returns (media_type, content_bytes) for any instance type.
    """
    raw = read_file(path, aes_key)

    if instance_type == 'IMAGE':
        ds = pydicom.dcmread(BytesIO(raw))
        arr = ds.pixel_array.astype(float)
        wc = float(getattr(ds, 'WindowCenter', arr.mean()))
        ww = float(getattr(ds, 'WindowWidth', arr.std() * 4 or 400))
        lo, hi = wc - ww / 2, wc + ww / 2
        arr = np.clip((arr - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr).convert('L')
        buf = BytesIO()
        img.save(buf, 'JPEG', quality=85)
        return 'image/jpeg', buf.getvalue()

    elif instance_type == 'SR':
        ds = pydicom.dcmread(BytesIO(raw))
        sr_dict = _dataset_to_dict(ds)
        html = _render_sr_to_html(sr_dict)
        return 'text/html', html.encode('utf-8')

    elif instance_type == 'NON_PIXEL':
        ds = pydicom.dcmread(BytesIO(raw))
        if hasattr(ds, 'EncapsulatedDocument'):
            return 'application/pdf', bytes(ds.EncapsulatedDocument)
        return 'application/json', json.dumps(_dataset_to_dict(ds)).encode()

    return 'application/octet-stream', raw
```

---

## 6. Authentication — User Creation, Login, Sessions

Authentication is unchanged from the original plan. JWT-based, bcrypt passwords, refresh tokens in DB.

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                     AUTHENTICATION FLOW                           │
  │                                                                   │
  │  STEP 1: SIGNUP                                                   │
  │  POST /api/auth/signup                                           │
  │  { "email", "password", "name", "phone", "role": "patient" }    │
  │  → bcrypt hash → INSERT users → 201                              │
  │                                                                   │
  │  STEP 2: LOGIN                                                    │
  │  POST /api/auth/login                                            │
  │  { "email", "password" }                                         │
  │  → bcrypt verify → access_token (1h JWT) + refresh_token (7d)   │
  │                                                                   │
  │  STEP 3: USE TOKEN                                               │
  │  GET /api/studies                                                │
  │  Authorization: Bearer eyJhbG...                                  │
  │  → JWT verify → request.user.email for all DB queries            │
  │                                                                   │
  │  STEP 4: REFRESH                                                  │
  │  POST /api/auth/refresh  { "refresh_token": "..." }              │
  │  → lookup + verify in refresh_tokens table → new access_token    │
  │                                                                   │
  │  STEP 5: LOGOUT                                                   │
  │  POST /api/auth/logout → DELETE refresh_token from DB            │
  └──────────────────────────────────────────────────────────────────┘
```

### Who Creates Which Users?

| Role | How they get an account |
|------|------------------------|
| patient | Self-signup via /signup page |
| doctor | Admin creates via /api/auth/create-user |
| technician | Admin creates (hospital staff only) |
| admin | Seeded via init script |

*(Full auth code is identical to original plan — see sections 6 of original)*

---

## 7. Data Isolation — "Only Their Own Data"

```
  ┌──────────────────────────────────────────────────────────────┐
  │                    DATA ISOLATION MODEL                        │
  │                                                                │
  │  LAYER 1: Authentication (who are you?)                       │
  │  POST /api/auth/login → JWT { sub: "patient@home.com" }      │
  │                                                                │
  │  LAYER 2: Ownership (what can you see?)                       │
  │  Every DB query:                                               │
  │    SELECT * FROM studies WHERE owner_email = jwt.email         │
  │                                                                │
  │  LAYER 3: Per-request Guard (double check)                    │
  │  Before serving any image/report/download:                    │
  │    if study.owner_email != jwt.email → 404                    │
  │                                                                │
  │  LAYER 4: Encryption (optional, defense in depth)             │
  │  If ENCRYPT_AT_REST=true:                                     │
  │    • Files are AES-256 encrypted on disk                      │
  │    • Keys are in Demo DB only, not in the files               │
  │    • Without key → raw bytes are unreadable                   │
  └──────────────────────────────────────────────────────────────┘

  ROLE VISIBILITY:
  ┌────────────┐    ┌─────────────────────────────────────────┐
  │ admin      │───▶│ All studies for their institution        │
  └────────────┘    └─────────────────────────────────────────┘
  ┌────────────┐    ┌─────────────────────────────────────────┐
  │ doctor     │───▶│ Studies assigned to them                 │
  └────────────┘    │ OR via study_assignments table           │
  ┌────────────┐    ┌─────────────────────────────────────────┐
  │ patient    │───▶│ Only their own uploads + shared results  │
  └────────────┘    │ WHERE owner_email = patient.email        │
```

---

## 8. Database Schema

### Why a Separate DB?

Same reasoning as before — zero risk to SPIN (now simply: zero risk to any other system), full schema freedom, clean backup.

### Schema

```sql
-- ============================================================
-- DEMO DATABASE — PostgreSQL :5432
-- ============================================================

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    role            VARCHAR(50) NOT NULL DEFAULT 'patient',
                    -- 'admin', 'doctor', 'patient', 'technician'
    institution     VARCHAR(255),
    phone           VARCHAR(20),
    created_at      TIMESTAMP DEFAULT NOW(),
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE studies (
    id              SERIAL PRIMARY KEY,
    study_uid       VARCHAR(255) UNIQUE NOT NULL,
    random_uid      VARCHAR(64) NOT NULL,
    owner_email     VARCHAR(255) NOT NULL REFERENCES users(email),
    patient_name    VARCHAR(255),
    patient_id      VARCHAR(64),
    study_date      DATE,
    modality        VARCHAR(16),
    description     VARCHAR(255),
    instance_count  INTEGER DEFAULT 0,
    series_count    INTEGER DEFAULT 0,
    image_count     INTEGER DEFAULT 0,
    sr_count        INTEGER DEFAULT 0,
    pdf_count       INTEGER DEFAULT 0,
    study_dir       VARCHAR(512) NOT NULL,
    thumbnail_path  VARCHAR(512),
    aes_key         BYTEA,                              -- NULL if ENCRYPT_AT_REST=false
    has_report      BOOLEAN DEFAULT FALSE,
    report_ready_at TIMESTAMP,
    is_deleted      BOOLEAN DEFAULT FALSE,
    deleted_at      TIMESTAMP,
    deleted_by      VARCHAR(255),
    status          VARCHAR(50) DEFAULT 'processing',
                    -- processing, ready, reported, failed
    source          VARCHAR(50) DEFAULT 'web',
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE instances (
    id              SERIAL PRIMARY KEY,
    study_id        INTEGER REFERENCES studies(id) ON DELETE CASCADE,
    series_folder   VARCHAR(64) NOT NULL,
    instance_file   VARCHAR(128) NOT NULL,
    sop_class_uid   VARCHAR(255),
    instance_type   VARCHAR(20) NOT NULL,       -- IMAGE, SR, NON_PIXEL
    instance_number INTEGER,
    is_report       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(study_id, series_folder, instance_file)
);

-- Doctor-patient study sharing
CREATE TABLE study_assignments (
    id              SERIAL PRIMARY KEY,
    study_id        INTEGER REFERENCES studies(id) ON DELETE CASCADE,
    assigned_to     VARCHAR(255) NOT NULL REFERENCES users(email),
    assigned_by     VARCHAR(255) NOT NULL REFERENCES users(email),
    role            VARCHAR(50) DEFAULT 'reviewer',  -- 'reviewer', 'reporter'
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(study_id, assigned_to)
);

CREATE TABLE web_uploads (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id),
    study_uid       VARCHAR(255),
    file_count      INTEGER DEFAULT 0,
    bytes_received  BIGINT DEFAULT 0,
    status          VARCHAR(50) DEFAULT 'uploading',
                    -- uploading, saving, ready, failed
    error_message   TEXT,
    uploaded_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE refresh_tokens (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL,
    expires_at      TIMESTAMP NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_studies_owner       ON studies(owner_email);
CREATE INDEX idx_studies_status      ON studies(status);
CREATE INDEX idx_studies_has_report  ON studies(has_report);
CREATE INDEX idx_studies_deleted     ON studies(is_deleted);
CREATE INDEX idx_instances_study     ON instances(study_id);
CREATE INDEX idx_instances_type      ON instances(instance_type);
CREATE INDEX idx_assignments_to      ON study_assignments(assigned_to);
```

### Schema Changes vs Original Plan

| Field | Change | Reason |
|-------|--------|--------|
| `forward_enabled` | **Removed** | No Orthanc forwarding |
| `forward_status` | **Removed** | No Orthanc forwarding |
| `forwarded_at` | **Removed** | No Orthanc forwarding |
| `counter_offset` | **Removed** | Was SPIN internal |
| `aes_key` | **Added** | Own AES key if ENCRYPT_AT_REST=true |
| `storage_backend` | **Not needed** | Only one backend now |

---

## 9. Study Registration — Direct DB Write (No Hook)

The original plan used a `post_finalize_hook` called by SPIN after OPT-44 re-finalization. Without SPIN, the upload route writes to the Demo DB directly (see Section 3 above). There is no separate hook file.

For re-uploads or additional instances to an existing study, use `ON CONFLICT (study_uid) DO UPDATE` as shown in the upload route.

### Study Deletion

```
  DELETE FLOW:

  User clicks [Delete] on study card
      │
      ▼
  Confirmation modal (unchanged from original)
      │
      ▼
  DELETE /api/studies/:id

  SOFT DELETE (default — patients/doctors):
  UPDATE studies SET is_deleted=true, deleted_at=NOW(), deleted_by=jwt.email
  WHERE id=:id AND owner_email=jwt.email
    → Study disappears from dashboard
    → Files on disk: UNTOUCHED

  HARD DELETE (admin only):
  DELETE FROM studies WHERE id=:id  (CASCADE deletes instances)
  # Optionally: shutil.rmtree(study['study_dir'])
```

```python
@router.delete("/{study_id}")
async def delete_study(study_id: int,
                        user=Depends(get_current_user),
                        db=Depends(get_db)):
    result = await db.execute("""
        UPDATE studies SET is_deleted=true, deleted_at=NOW(), deleted_by=$1
        WHERE id=$2 AND owner_email=$1 AND is_deleted=false
    """, user['email'], study_id)
    if result == 'UPDATE 0':
        raise HTTPException(404)
    return {"status": "deleted"}

@router.delete("/{study_id}/hard")
async def hard_delete_study(study_id: int,
                             user=Depends(require_admin),
                             db=Depends(get_db)):
    study = await db.fetchrow("SELECT * FROM studies WHERE id=$1", study_id)
    if not study:
        raise HTTPException(404)
    await db.execute("DELETE FROM studies WHERE id=$1", study_id)
    # shutil.rmtree(study['study_dir'], ignore_errors=True)  # optional
    return {"status": "hard_deleted", "study_uid": study['study_uid']}
```

---

## 10. Study List & Forward Controls

The `forward_*` columns and Orthanc forwarding endpoint are removed. Study list query is unchanged otherwise.

```sql
-- GET /api/studies always uses:
SELECT * FROM studies
WHERE owner_email = $1
  AND is_deleted = false
ORDER BY created_at DESC;
```

---

## 11. Two Deployment Modes

### Mode 1: Local Demo (Everything on Your PC)

No SPIN, no Orthanc. Your PC runs the Demo App and stores files locally. Caddy gives you real HTTPS.

```
  ┌────────────────────────────────────────────────────────────────┐
  │               YOUR PC (public IP: x.x.x.x)                    │
  │                                                                 │
  │  INTERNET ──▶ Caddy :443 ──▶ Demo FastAPI :8080               │
  │  (demo from      (auto TLS)                                    │
  │   any browser)                                                  │
  │                                                                 │
  │  ┌─────────────┐  ┌──────────┐  ┌─────────────────────────┐  │
  │  │ Demo FastAPI │  │ Demo DB  │  │ Local Storage           │  │
  │  │ :8080       │  │ :5432    │  │ D:\demoData\dcm\...     │  │
  │  └─────────────┘  └──────────┘  └─────────────────────────┘  │
  │                                                                 │
  │  Access:                                                        │
  │    Patient view: https://demo.yourdomain.com                   │
  │    Or:           http://localhost:8080 (for quick testing)     │
  └────────────────────────────────────────────────────────────────┘

  Start order:
    1. PostgreSQL (:5432)
    2. Demo FastAPI (python run.py)
    3. Caddy (caddy run --config Caddyfile)

  Demo test flow:
    1. Open https://demo.yourdomain.com → signup as patient@test.com
    2. Upload .dcm files via drag-and-drop
    3. Study appears immediately on dashboard (no SPIN processing delay)
    4. Log in as doctor → open study → view images
    5. Doctor uploads report PDF via admin panel
    6. Patient refreshes → "Report Available" badge
    7. Patient clicks → views PDF report
```

### Mode 2: Ruby Hall Production

SPIN is not required. The Demo App runs on a physical server at Ruby Hall, behind Caddy. Storage is on the server's disk.

```
  ┌────────────────────────────────────────────────────────────────┐
  │              RUBY HALL HOSPITAL (physical server)               │
  │                                                                 │
  │  INTERNET ──▶ Caddy :443 ──▶ Demo FastAPI :8080               │
  │  (patients,      (TLS)       (web pages + API)                 │
  │   referring                                                     │
  │   doctors)                                                      │
  │                                                                 │
  │  ┌──────────────────────────────────────────────────────────┐  │
  │  │  Services (all on same server):                          │  │
  │  │                                                           │  │
  │  │  Caddy :443          ← internet-facing (TLS)             │  │
  │  │  Demo FastAPI :8080  ← behind Caddy (localhost only)     │  │
  │  │  Demo DB :5432       ← localhost only                    │  │
  │  └──────────────────────────────────────────────────────────┘  │
  │                                                                 │
  │  Firewall:                                                      │
  │    :443   → open to internet (HTTPS for patients)              │
  │    :80    → open to internet (→ redirect to 443)               │
  │    everything else → localhost only                             │
  └────────────────────────────────────────────────────────────────┘
```

### Caddyfile (works for both modes)

```
# demo/scripts/Caddyfile

demo.yourdomain.com {
    reverse_proxy localhost:8080

    @static path /static/*
    header @static Cache-Control "public, max-age=604800"

    header {
        X-Content-Type-Options nosniff
        X-Frame-Options SAMEORIGIN
        Referrer-Policy strict-origin-when-cross-origin
    }

    request_body {
        max_size 500MB
    }
}
```

```
# demo/scripts/Caddyfile.local
:8443 {
    tls internal
    reverse_proxy localhost:8080
}
```

---

## 12. Performance — File Serving

Without AES encryption (default), serving is pure I/O + JPEG encode. With ENCRYPT_AT_REST=true, add ~2ms per file.

```
  SERVE PIPELINE (per image, no encryption):

  ┌─────────┐   ┌──────────┐   ┌──────────┐
  │ Read    │──▶│ Pixel    │──▶│ JPEG     │   Total: ~12ms
  │ .dcm    │   │ decode   │   │ encode   │
  │  ~1ms   │   │  ~7ms    │   │  ~4ms    │
  └─────────┘   └──────────┘   └──────────┘

  WITH ENCRYPT_AT_REST=true:

  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
  │ Read    │──▶│ AES-CTR  │──▶│ Pixel    │──▶│ JPEG     │   Total: ~14ms
  │ .enc    │   │ decrypt  │   │ decode   │   │ encode   │
  │  ~1ms   │   │  ~2ms    │   │  ~7ms    │   │  ~4ms    │
  └─────────┘   └──────────┘   └──────────┘   └──────────┘

  FOR SR/PDF:
  ┌─────────┐   ┌──────────┐
  │ Read    │──▶│ Parse /  │   Total: ~4ms (no encryption)
  │  file   │   │ serve    │
  │  ~1ms   │   │  ~3ms    │
  └─────────┘   └──────────┘
```

| Scenario | Time | UX |
|----------|------|----|
| View 1 CT slice | ~12ms | Instant |
| Scroll 100 slices (prefetch) | ~1.2s pipelined | Smooth |
| View SR report | ~4ms | Instant |
| View PDF report | ~4ms | Instant |
| Download 500-instance ZIP | ~6s | Progress bar |
| Upload 500 instances via browser | ~20s (HTTP, no C-STORE hop) | Progress bar |

**Browser gets plain JPEG/HTML/PDF — no crypto in frontend.**

---

## 13. Project Structure

```
demo/
├── DEMO_PLAN.md
├── requirements.txt
├── .env.example
├── .env.local                          ← Local demo config
├── run.py                              ← Entry: uvicorn launcher
│
├── api/
│   ├── __init__.py
│   ├── main.py                         ← FastAPI app + static mount + templates
│   ├── config.py                       ← Load from .env
│   ├── dependencies.py                 ← get_db(), get_current_user()
│   │
│   ├── auth/
│   │   ├── routes.py                   ← signup, login, refresh, me
│   │   ├── jwt_handler.py
│   │   ├── password.py                 ← bcrypt
│   │   └── schemas.py
│   │
│   ├── studies/
│   │   ├── routes.py                   ← list, detail, delete, report upload
│   │   ├── service.py                  ← Ownership checks
│   │   └── schemas.py
│   │
│   ├── viewer/
│   │   ├── routes.py                   ← image, sr, pdf endpoints
│   │   ├── decrypt_helper.py           ← Read + optional AES decrypt + serve
│   │   └── crypto.py                   ← AES-256-CTR (only if ENCRYPT_AT_REST=true)
│   │
│   ├── upload/
│   │   ├── routes.py                   ← POST /upload, status
│   │   └── local_storage.py            ← Save .dcm to disk, register in DB
│   │
│   ├── download/
│   │   └── routes.py                   ← ZIP stream download
│   │
│   └── db/
│       ├── connection.py               ← Connection pool
│       └── migrations/
│           └── 001_init.sql
│
├── web/
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── viewer.html                 ← Cornerstone.js viewer
│   │   ├── report.html
│   │   ├── upload.html
│   │   ├── admin.html                  ← Includes report upload form for doctors
│   │   └── errors/
│   │       ├── 404.html
│   │       └── 500.html
│   │
│   └── static/
│       ├── css/styles.css
│       ├── js/
│       │   ├── auth.js
│       │   ├── api.js
│       │   ├── dashboard.js
│       │   ├── viewer.js
│       │   ├── upload.js
│       │   ├── report.js
│       │   ├── admin.js
│       │   └── theme.js
│       └── assets/
│           ├── logo.svg
│           └── favicon.ico
│
└── scripts/
    ├── init_db.py                      ← Create demo DB + tables
    ├── seed_users.py                   ← Test users for demo
    ├── Caddyfile
    ├── Caddyfile.local
    └── start_local.sh
```

**Removed vs original:**
- `demo/hooks/post_finalize.py` — not needed, DB write is in upload route
- `demo/api/upload/dicom_bridge.py` — replaced by `local_storage.py`

**Added:**
- `demo/api/viewer/crypto.py` — optional AES layer
- Report upload endpoint in `studies/routes.py`

---

## 14. Web Pages — Layouts, Wireframes & Styling

All pages are identical to the original plan with one addition: the **admin panel** gets a "Upload Report" form on the study detail view.

```
  admin.html — STUDIES TAB (with report upload):

  ┌──────────────────────────────────────────────────────────────┐
  │  [Users]  [Studies]  [System]                                │
  ├──────────────────────────────────────────────────────────────┤
  │  All studies across all users                                │
  │  ┌────────┬───────────┬──────────┬─────────┬──────┬──────┐  │
  │  │ Patient│ Modality  │ Owner    │ Status  │Report│      │  │
  │  ├────────┼───────────┼──────────┼─────────┼──────┼──────┤  │
  │  │ Rahul  │ CT Chest  │ dr.shah  │ Ready   │  No  │[↑]   │  │
  │  │ Meera  │ MR Brain  │ dr.patel │Reported │  Yes │[↑]   │  │
  │  └────────┴───────────┴──────────┴─────────┴──────┴──────┘  │
  │                                                              │
  │  [↑] = "Upload Report" button → opens modal:                │
  │  ┌──────────────────────────────────────────────────────┐   │
  │  │  Upload Report for: CT Chest — Rahul Sharma          │   │
  │  │                                                      │   │
  │  │  [ Drop PDF or DICOM SR here, or click to browse ]  │   │
  │  │                                                      │   │
  │  │              [Cancel]  [Upload Report]               │   │
  │  └──────────────────────────────────────────────────────┘   │
  └──────────────────────────────────────────────────────────────┘

  admin.html — SYSTEM TAB (updated):

  ┌──────────────────────────────────────────────────────────────┐
  │  Demo DB: ● Connected (:5432)                                │
  │  Storage: D:\demoData\dcm\  — 14.2 GB used                  │
  │  Encrypt at rest: OFF  (set ENCRYPT_AT_REST=true to enable)  │
  │  Studies: 47  |  Users: 12  |  Uploads today: 3             │
  └──────────────────────────────────────────────────────────────┘
```

---

## 15. API Endpoints

### Auth

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/auth/signup` | Create account | No |
| POST | `/api/auth/login` | JWT + refresh token | No |
| POST | `/api/auth/refresh` | New JWT | Refresh |
| GET | `/api/auth/me` | Current user | JWT |

### Studies

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/studies` | User's studies (excludes soft-deleted) | JWT |
| GET | `/api/studies/:id` | Study detail + instance list | JWT |
| GET | `/api/studies/:id/download` | Files as ZIP stream | JWT |
| DELETE | `/api/studies/:id` | Soft-delete | JWT (owner) |
| DELETE | `/api/studies/:id/hard` | Hard-delete + files | JWT (admin) |
| POST | `/api/studies/:id/report` | Upload PDF/SR report | JWT (doctor/admin) |

*Note: `/api/studies/:id/forward` and `/api/studies/:id/forward/status` are removed — no Orthanc.*

### Viewer

| Method | Path | Description | Returns |
|--------|------|-------------|---------|
| GET | `/api/viewer/:id/thumbnail` | Thumbnail | image/jpeg |
| GET | `/api/viewer/:id/:series/:instance` | Single image | image/jpeg |
| GET | `/api/viewer/:id/report` | SR as HTML or PDF binary | text/html / application/pdf |
| GET | `/api/viewer/:id/report/pdf` | Force PDF download | application/pdf |

### Upload

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/upload` | Upload DICOM files (multipart) | JWT |
| GET | `/api/upload/:id/status` | Upload status | JWT |

### Pages (Jinja2)

| Path | Page |
|------|------|
| `/` | Landing |
| `/login` | Login / Signup |
| `/dashboard` | Study list with report badges |
| `/viewer/:id` | Image viewer (Cornerstone.js) |
| `/report/:id` | Report viewer (SR/PDF) |
| `/upload` | Drag-and-drop upload |
| `/admin` | Admin panel (doctor/admin only) |

---

## 16. Technology Stack

```
  BACKEND                           FRONTEND
  ───────                           ────────
  Python 3.11+                      Jinja2 templates (SSR)
  FastAPI                           Tailwind CSS
  Uvicorn (ASGI)                    Vanilla JS
  asyncpg (PostgreSQL)              Cornerstone.js (DICOM viewer)
  PyJWT + bcrypt                    pdf.js (PDF viewer)
  pydicom (DICOM parse + serve)
  Pillow (JPEG encode, thumbnails)
  cryptography (optional AES)

  INFRASTRUCTURE
  ──────────────
  PostgreSQL 15 (:5432)             Caddy (TLS + reverse proxy)
  systemd / NSSM (service mgmt)
```

**Removed vs original:**
- `pynetdicom` — no DICOM C-STORE needed
- `PAX modules` — no SPIN decryptor
- Orthanc — no workstation simulator required
- SPIN DB (`psycopg2` read-only connection) — no brix access

---

## 17. Implementation Phases

### Phase 1: Foundation (Week 1)

```
  [ ] demo/ folder structure
  [ ] PostgreSQL :5432 setup
  [ ] 001_init.sql — create all tables (updated schema above)
  [ ] FastAPI skeleton: main.py, config, static mount, Jinja2
  [ ] Auth: signup, login, JWT, refresh
  [ ] base.html template with nav/auth
  [ ] Login page
  [ ] Seed script with test users
  [ ] .env.local for local demo mode
```

### Phase 2: Study List + Direct Registration (Week 2)

```
  [ ] local_storage.py — save_dicom_files(), _generate_thumbnail()
  [ ] Upload route → save to disk → INSERT into studies/instances
  [ ] GET /api/studies — filtered by owner_email
  [ ] Dashboard page with study cards
  [ ] Study detail page (series list, instance types)
  [ ] "Report Available" badge on dashboard
```

### Phase 3: Viewer + Reports (Week 3)

```
  [ ] decrypt_helper.py — IMAGE/SR/PDF serve (plain + optional AES)
  [ ] Image viewer endpoint + Cornerstone.js page
  [ ] SR report renderer (ContentSequence → HTML tree)
  [ ] PDF report viewer (read → serve as application/pdf)
  [ ] Report page (auto-detect SR vs PDF by file extension)
  [ ] Download endpoint (files → ZIP stream)
```

### Phase 4: Report Upload + Doctor Flow (Week 4)

```
  [ ] POST /api/studies/:id/report endpoint
  [ ] Doctor report upload UI in admin panel (modal or dedicated page)
  [ ] Test: upload study → doctor views images → doctor uploads report
  [ ]        patient sees "Report Available" → patient views report
  [ ] Optional: enable ENCRYPT_AT_REST=true, test full encrypt/decrypt cycle
```

### Phase 5: Production Deploy (Week 5)

```
  [ ] Caddy config with domain + TLS
  [ ] Firewall rules (:443 only public)
  [ ] Role-based access (admin/doctor/patient)
  [ ] Study assignment (doctor ↔ patient)
  [ ] Rate limiting
  [ ] Error pages (404, 500)
  [ ] Start scripts (systemd or NSSM on Windows)
  [ ] Full cycle test with real data
```

---

## 18. Open Questions

| # | Question | Default Assumption |
|---|----------|--------------------|
| 1 | Single PG database or separate schema? | Single DB `demo`, single schema |
| 2 | How does the doctor submit the report — browser upload or API? | Browser upload via admin panel (Phase 4) |
| 3 | Does the patient need to see images too, or only the final report? | Both — images in Cornerstone.js viewer, report separately |
| 4 | Payment gateway choice? | Razorpay — deferred to Phase 6 |
| 5 | Multi-hospital support? | Single for now, schema supports multi |
| 6 | Domain name for production? | TBD — Caddy handles any domain |
| 7 | Encrypt at rest? | Off by default for demo, toggle via ENCRYPT_AT_REST=true |
| 8 | What if the hospital wants DICOM modality integration later? | Add a thin DICOM receiver (pynetdicom SCP) as a separate service that calls the same `save_dicom_files()` function |

---

## 19. Config

```env
# demo/.env.example

# === Demo App ===
DEMO_HOST=0.0.0.0
DEMO_PORT=8080
DEMO_SECRET_KEY=change-me

# === JWT ===
JWT_SECRET=change-me
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRE_MINUTES=60
JWT_REFRESH_EXPIRE_DAYS=7

# === Demo Database ===
DEMO_DB_HOST=localhost
DEMO_DB_PORT=5432
DEMO_DB_NAME=demo
DEMO_DB_USER=demo
DEMO_DB_PASSWORD=change-me

# === Local Storage ===
LOCAL_DATA_DIR=D:/demoData/dcm

# === Encryption (optional) ===
# Set to "true" to enable AES-256-CTR at-rest encryption
# Keys stored in Demo DB (studies.aes_key column)
ENCRYPT_AT_REST=false

# === Deployment Mode ===
# "local" = no TLS, localhost only
# "production" = behind Caddy, public IP
DEPLOY_MODE=local

# === Caddy (production only) ===
DOMAIN=demo.yourdomain.com

# === Upload Limits ===
MAX_UPLOAD_SIZE_MB=500
MAX_UPLOADS_PER_HOUR=10
```

**Removed vs original:**
- `SPIN_DB_*` — no brix DB access
- `SPIN_AE_TITLE`, `SPIN_HOST`, `SPIN_PORT` — no DICOM server
- `DEMO_AE_TITLE` — no SCU registration
- `ORTHANC_URL` — no workstation simulator

---

## 20. Summary

```
  ┌──────────────────────────────────────────────────────────────┐
  │                    WHAT WE'RE BUILDING                        │
  │                                                               │
  │  A standalone web app that handles the FULL diagnostic cycle  │
  │  with NO external DICOM server required:                      │
  │                                                               │
  │  UPLOAD ──▶ STORE ──▶ REVIEW ──▶ REPORT ──▶ DELIVER         │
  │  (patient    (disk +   (doctor    (doctor    (patient sees    │
  │   from home  demo DB)  in viewer  uploads    report on web,   │
  │   via browser)         via browser PDF/SR)   from anywhere)   │
  │                                                               │
  │  Key architecture:                                            │
  │  • No SPIN, no Orthanc, no named PACS server                │
  │  • Files saved directly to LOCAL_DATA_DIR on disk            │
  │  • Demo DB is the single source of truth                     │
  │  • Optional AES-256 at-rest encryption (own key in DB)       │
  │  • Report upload: doctor submits PDF/SR via browser          │
  │  • Server-side JPEG encode (~12ms/image, ~4ms/report)        │
  │  • Caddy for TLS (auto HTTPS)                                │
  │                                                               │
  │  Two deployment modes:                                        │
  │  • Local demo: one PC, Caddy + domain, full cycle in minutes │
  │  • Production: physical server, Caddy exposes web portal     │
  │                                                               │
  │  Internet ──▶ Caddy ──▶ Demo API ──▶ Demo DB                │
  │                                  └──▶ Local Storage (disk)   │
  │                                                               │
  │  Future DICOM integration (optional):                         │
  │  Add a thin pynetdicom SCP service that calls                │
  │  save_dicom_files() — same storage, same DB, same viewer.    │
  └──────────────────────────────────────────────────────────────┘
```
