# Hospital PACS — Frontend Build Guide

> **Stack recommendation:** HTML, CSS, JS, BOOTSTRAP  
> **Design theme:** Clean white background, red/yellow/green/blue action buttons, card-based layout

---

## 1. Design Principles

| Principle | Detail |
|-----------|--------|
| Background | Pure white (`#FFFFFF`) with light gray page backdrop (`#F8F9FA`) |
| Font | Inter or Poppins — clean, medical-friendly |
| Borders | Subtle `1px solid #E5E7EB` on cards; `rounded-xl` corners |
| Shadows | `shadow-sm` for cards, `shadow-md` on hover |
| Spacing | Generous padding (`p-6` to `p-8` on cards) |

### Button Color Semantics

| Color | Hex | Usage |
|-------|-----|-------|
| 🔵 Blue | `#2563EB` | Primary actions (Login, View, Search, Load Orthanc) |
| 🟢 Green | `#16A34A` | Success / confirm actions (Save Study, Send to Orthanc, Register) |
| 🟡 Yellow | `#D97706` | Warning / secondary actions (Preview, Edit, Pending status badge) |
| 🔴 Red | `#DC2626` | Destructive actions (Delete, Logout) |

---

## 2. Page & Component Map

```
/login              → LoginPage
/register           → RegisterPage
/dashboard          → DashboardPage
  ├── UploadCard         (DICOM upload form)
  ├── PdfUploadCard      (doctors only, shown conditionally)
  ├── StudyList          (previously uploaded studies)
  └── StudyCard          (thumbnail + metadata + action buttons)
/study/:id          → StudyDetailPage
  ├── DicomMetaTable
  ├── ThumbnailViewer
  ├── PdfReportList
  └── ActionBar          (Send to Orthanc | Download for RadiAnt | Delete)
/orthanc            → OrthancBrowserPage
  ├── OrthancHealthBadge
  └── OrthancStudyList
```

---

## 3. Auth Flow

```
LoginPage
  ├── POST /auth/login  (form: username, password)

RegisterPage
  ├── GET /users/roles  (populate role selector)
  └── POST /auth/register
  └── Redirect → /login
```

---

## 4. Dashboard Page Layout

```
┌───────────────────────────────────────────────────────────────┐
│  🏥 Hospital PACS                          [Logout 🔴]         │
│  Welcome, Dr. John — Role: Doctor                             │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─── Upload New Study ────────────────────────────────────┐  │
│  │                                                         │  │
│  │  MR Number: [________________]                          │  │
│  │                                                         │  │
│  │  DICOM File: [  Choose .dcm file  ] 🟡 (all users)     │  │
│  │                                                         │  │
│  │  ── Doctors only ────────────────────────────────────── │  │
│  │  PDF Report: [  Choose .pdf file  ] (optional)          │  │
│  │  Notes:      [________________]                          │  │
│  │                                                         │  │
│  │               [🔵 Upload & Preview]                     │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│  ── Your Previous Studies ────────────────────────────────── │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  [thumbnail] │  │  [thumbnail] │  │  [thumbnail] │        │
│  │  MR: A10023  │  │  MR: B20044  │  │  MR: C30011  │        │
│  │  John Doe    │  │  Jane Smith  │  │  Bob Jones   │        │
│  │  Age: 45Y    │  │  Age: 32Y    │  │  Age: 67Y    │        │
│  │  CT  |  Chest│  │  MR  |  Brain│  │  CR  |  Chest│        │
│  │  2024-12-01  │  │  2024-11-15  │  │  2024-10-30  │        │
│  │ [🔵 View]    │  │ [🔵 View]    │  │ [🔵 View]    │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└───────────────────────────────────────────────────────────────┘
```

---

## 5. Upload Preview Page (after DICOM upload)

```
┌─────────────────────────────────────────────────────────────────┐
│  📋 Study Preview — Please confirm before saving                 │
├───────────────────────┬─────────────────────────────────────────┤
│                       │  Patient Name : JOHN DOE                │
│   [DICOM Thumbnail]   │  MR Number    : [  A10023  ]  ← editable│
│   256 × 256 px        │  Patient ID   : PID-001                 │
│                       │  Age / DOB    : 045Y / 1979-03-12       │
│                       │  Sex          : M                       │
│                       ├─────────────────────────────────────────┤
│                       │  Modality     : CT                      │
│                       │  Body Part    : CHEST                   │
│                       │  Study Date   : 20241201                │
│                       │  Description  : Chest CT with contrast  │
│                       │  Accession #  : ACC-20241201-001        │
│                       │  Study UID    : 1.2.840.xxxxx           │
│                       │  File Size    : 2.34 MB                 │
├───────────────────────┴─────────────────────────────────────────┤
│          [🔴 Cancel]        [🟢 Save to PACS]                   │
└─────────────────────────────────────────────────────────────────┘
```

**API calls:**
1. `POST /dicom/upload` (FormData: `mr_number`, `dicom_file`) → show preview
2. `POST /dicom/confirm/{temp_study_id}` (body: `{ "mr_number": "A10023" }`) → save

---

## 6. Study Detail Page

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Back to Dashboard          Study: CT Chest — John Doe        │
├───────────────────────┬─────────────────────────────────────────┤
│                       │  All DICOM metadata in a clean table    │
│  [Large Thumbnail]    │  (same fields as preview + UID fields)  │
│                       ├─────────────────────────────────────────┤
│                       │  PDF Reports (if any)                   │
│                       │  📄 report_2024.pdf    [🔵 Download]    │
│                       │  📄 followup.pdf       [🔵 Download]    │
├───────────────────────┴─────────────────────────────────────────┤
│  Action Bar                                                     │
│  [🟢 Send to Orthanc]  [🔵 Download for RadiAnt]  [🔴 Delete]  │
└─────────────────────────────────────────────────────────────────┘
```

- **Send to Orthanc** → `POST /orthanc/send/{study_id}`  
  Show a 🟢 success toast with the Orthanc study ID, or 🔴 error toast
- **Download for RadiAnt** → `GET /dicom/download/{study_id}` (browser download)  
  Show a tooltip: *"Save the file, then drag and drop it onto RadiAnt Viewer"*
- **Delete** → confirm dialog → `DELETE /dicom/studies/{study_id}`

---

## 7. Orthanc Browser Page

```
┌─────────────────────────────────────────────────────────────────┐
│  Orthanc PACS Browser                                           │
│  Status: 🟢 Online  |  Version: 1.12.x  |  [🔵 Refresh]       │
├─────────────────────────────────────────────────────────────────┤
│  Patient Name     │ Study Date │ Modality │ Description │ Action│
│  ─────────────────┼────────────┼──────────┼─────────────┼───── │
│  JOHN DOE         │ 20241201   │ CT       │ Chest CT    │[View] │
│  JANE SMITH       │ 20241115   │ MR       │ Brain MRI   │[View] │
└─────────────────────────────────────────────────────────────────┘
```

---


## 9. Color Palette Reference

```
Backgrounds:  bg-white, bg-gray-50, bg-gray-100
Cards:        bg-white border border-gray-200 rounded-xl shadow-sm
Text primary: text-gray-900
Text muted:   text-gray-500

🔵 Blue button:   bg-blue-600 hover:bg-blue-700 text-white
🟢 Green button:  bg-green-600 hover:bg-green-700 text-white
🟡 Yellow button: bg-yellow-500 hover:bg-yellow-600 text-white
🔴 Red button:    bg-red-600 hover:bg-red-700 text-white

All buttons:  px-4 py-2 rounded-lg font-medium transition-colors duration-150
```

---


## 11. Key API Endpoints Summary

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | ❌ | Register new user |
| POST | `/auth/login` | ❌ | Login → JWT |
| GET | `/auth/me` | ✅ | Own profile |
| GET | `/users/roles` | ❌ | List roles |
| POST | `/dicom/upload` | ✅ | Upload DICOM → preview |
| POST | `/dicom/confirm/{id}` | ✅ | Save study permanently |
| GET | `/dicom/studies` | ✅ | List own studies |
| GET | `/dicom/studies/{id}` | ✅ | Study detail |
| GET | `/dicom/thumbnail/{id}` | ✅ | Thumbnail image |
| GET | `/dicom/download/{id}` | ✅ | Download DICOM |
| DELETE | `/dicom/studies/{id}` | ✅ | Delete study |
| POST | `/dicom/upload-pdf/{id}` | ✅ Doctor | Attach PDF |
| GET | `/orthanc/health` | ❌ | Orthanc status |
| POST | `/orthanc/send/{id}` | ✅ | Send to Orthanc |
| GET | `/orthanc/studies` | ✅ | List Orthanc studies |
| GET | `/orthanc/download/{id}` | ✅ | Download via Orthanc |
| GET | `/orthanc/radiant-instructions` | ✅ | RadiAnt setup guide |