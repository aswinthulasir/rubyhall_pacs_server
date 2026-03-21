/**
 * pages/dashboard.js — Dashboard Page
 * Upload DICOM + View previous studies
 */

async function renderDashboardPage(container) {
  const user = getUser();
  const isDoctor = user && user.role_id === 2;

  container.innerHTML = `
    ${renderNavbar()}
    <div class="page-content">

      <!-- Upload Card -->
      <div class="card" style="margin-bottom: 2rem;">
        <div class="card-header">
          <h3>📤 Upload New Study</h3>
        </div>
        <div class="card-body">
          <form id="upload-form">
            <div class="form-group" style="margin-bottom:0;">
              <label>DICOM File(s) (.dcm)</label>
              <div class="file-upload-area" id="dicom-drop-area" onclick="document.getElementById('upload-dicom').click()">
                <div class="upload-icon">📁</div>
                <div class="upload-text" id="dicom-file-label">Click to choose .dcm files</div>
              </div>
              <input type="file" id="upload-dicom" accept=".dcm,application/dicom,application/octet-stream"
                     style="display:none" required multiple>
            </div>

            ${isDoctor ? `
            <div class="doctor-section">
              <div class="doctor-section-label">🩺 Doctors Only — Attach PDF Report</div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem;">
                <div class="form-group" style="margin-bottom:0;">
                  <label>PDF Report (optional)</label>
                  <div class="file-upload-area" onclick="document.getElementById('upload-pdf').click()">
                    <div class="upload-icon">📄</div>
                    <div class="upload-text" id="pdf-file-label">Click to choose a .pdf file</div>
                  </div>
                  <input type="file" id="upload-pdf" accept=".pdf,application/pdf" style="display:none">
                </div>
                <div class="form-group" style="margin-bottom:0;">
                  <label for="upload-notes">Notes</label>
                  <input type="text" class="form-control" id="upload-notes"
                         placeholder="Optional report notes" style="margin-top: 0.25rem; height: calc(100% - 1.8rem);">
                </div>
              </div>
            </div>
            ` : ''}

            <div style="margin-top: 1.5rem;">
              <button type="submit" class="btn btn-blue btn-lg" id="btn-upload">
                📤 Upload & Preview
              </button>
            </div>
          </form>
        </div>
      </div>

      <!-- Preview Area (shown after upload) -->
      <div id="preview-area" style="display:none;"></div>

      <!-- Studies List -->
      <div class="section-divider">📋 Your Previous Studies</div>
      <div id="studies-container">
        <div style="text-align:center; padding: 2rem;">
          <div class="spinner spinner-dark" style="width:32px;height:32px;border-width:3px;margin: 0 auto 0.75rem;"></div>
          <div class="text-muted">Loading studies…</div>
        </div>
      </div>
    </div>
  `;

  // File input label updates
  document.getElementById('upload-dicom').addEventListener('change', (e) => {
    const files = e.target.files;
    const label = document.getElementById('dicom-file-label');
    if (files.length === 1) {
      label.className = 'file-selected';
      label.textContent = `✓ ${files[0].name}`;
    } else if (files.length > 1) {
      label.className = 'file-selected';
      label.textContent = `✓ ${files.length} files selected`;
    }
  });

  if (isDoctor) {
    const pdfInput = document.getElementById('upload-pdf');
    if (pdfInput) {
      pdfInput.addEventListener('change', (e) => {
        const name = e.target.files[0]?.name;
        const label = document.getElementById('pdf-file-label');
        if (name) {
          label.className = 'file-selected';
          label.textContent = `✓ ${name}`;
        }
      });
    }
  }

  // Upload form
  document.getElementById('upload-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('btn-upload');
    const dicomFiles = document.getElementById('upload-dicom').files;

    if (dicomFiles.length === 0) {
      showToast('Please select DICOM file(s)', 'warning');
      return;
    }

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Uploading…';

    try {
      const preview = await apiUploadDicomMulti(dicomFiles);
      showToast(`${dicomFiles.length} file(s) uploaded! Review the preview below.`, 'success');
      renderPreview(preview, isDoctor);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '📤 Upload & Preview';
    }
  });

  // Load studies
  loadStudies();
}

/* ── Render DICOM preview ──────────────────────────────────────────────── */
function renderPreview(data, isDoctor) {
  const area = document.getElementById('preview-area');
  area.style.display = 'block';
  area.scrollIntoView({ behavior: 'smooth', block: 'start' });

  area.innerHTML = `
    <div class="card" style="margin-bottom: 2rem; border-color: var(--blue); border-width: 2px;">
      <div class="card-header" style="background: var(--brand-light);">
        <h3>📋 Study Preview — Confirm before saving</h3>
        <span class="badge badge-yellow">PENDING</span>
      </div>
      <div class="card-body">
        <div class="preview-layout">
          <div class="preview-thumbnail">
            ${data.thumbnail_url
              ? `<img data-auth-src="${data.thumbnail_url}" alt="DICOM Thumbnail" class="auth-img"
                       onerror="this.parentElement.innerHTML='<div class=\\'thumb-placeholder\\'>🩻</div>'">`
              : '<div class="thumb-placeholder">🩻</div>'}
          </div>
          <div>
            <table class="meta-table">
              <tr><td>Patient Name</td><td><strong style="font-size:1.05rem;">${escapeHtml(data.patient_name) || '—'}</strong></td></tr>
              <tr><td>File(s)</td><td>${escapeHtml(data.file_name) || '1 file'}</td></tr>
              <tr><td>Total Size</td><td>${formatFileSize(data.file_size_kb)}</td></tr>
              <tr><td>Patient ID</td><td>${escapeHtml(data.patient_id_dicom) || '—'}</td></tr>
              <tr><td>Age / DOB</td><td>${escapeHtml(data.patient_age) || '—'} / ${escapeHtml(data.patient_dob) || '—'}</td></tr>
              <tr><td>Sex</td><td>${escapeHtml(data.patient_sex) || '—'}</td></tr>
              <tr><td>Modality</td><td>${escapeHtml(data.modality) || '—'}</td></tr>
            </table>
          </div>
        </div>
      </div>
      <div class="action-bar">
        <button class="btn btn-red" id="btn-cancel-preview" onclick="cancelPreview()">🔴 Cancel</button>
        <button class="btn btn-green btn-lg" id="btn-confirm" onclick="confirmBatch()">
          🟢 Save to PACS
        </button>
      </div>
    </div>
  `;

  // Load authenticated images
  loadAllAuthImages(area);

  // Store preview data for potential PDF upload
  window._lastPreview = data;
}

function cancelPreview() {
  const area = document.getElementById('preview-area');
  area.style.display = 'none';
  area.innerHTML = '';
}

async function confirmBatch() {
  const btn = document.getElementById('btn-confirm');

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Saving All…';

  try {
    const studies = await apiConfirmBatch();
    showToast(`${studies.length} studies saved to PACS! ✓`, 'success');

    // If doctor has a PDF attached, upload it to the FIRST study in the batch
    const user = getUser();
    if (user && user.role_id === 2 && studies.length > 0) {
      const pdfInput = document.getElementById('upload-pdf');
      if (pdfInput && pdfInput.files[0]) {
        const notes = document.getElementById('upload-notes')?.value || '';
        try {
          await apiUploadPdf(studies[0].id, pdfInput.files[0], notes);
          showToast('PDF report attached ✓', 'success');
        } catch (err) {
          showToast(`PDF upload failed: ${err.message}`, 'warning');
        }
      }
    }

    cancelPreview();
    // Reset form
    document.getElementById('upload-form').reset();
    const dicomLabel = document.getElementById('dicom-file-label');
    if (dicomLabel) { dicomLabel.className = 'upload-text'; dicomLabel.textContent = 'Click to choose .dcm files'; }
    const pdfLabel = document.getElementById('pdf-file-label');
    if (pdfLabel) { pdfLabel.className = 'upload-text'; pdfLabel.textContent = 'Click to choose a .pdf file'; }

    loadStudies();
  } catch (err) {
    showToast(err.message, 'error');
    btn.disabled = false;
    btn.innerHTML = '🟢 Save All to PACS';
  }
}

/* ── Load and render studies ───────────────────────────────────────────── */
async function loadStudies() {
  const container = document.getElementById('studies-container');
  try {
    const studies = await apiGetStudies();

    if (studies.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📭</div>
          <h4>No Studies Yet</h4>
          <p>Upload your first DICOM study using the form above.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = `<div class="study-grid">${studies.map(renderStudyCard).join('')}</div>`;

    // Load authenticated thumbnail images
    loadAllAuthImages(container);
  } catch (err) {
    if (err.message === 'Session expired') {
      showToast('Session expired. Please log in again.', 'error');
      clearToken();
      navigateTo('login');
      router();
      return;
    }
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚠️</div>
        <h4>Error Loading Studies</h4>
        <p>${escapeHtml(err.message)}</p>
      </div>
    `;
  }
}

function renderStudyCard(study) {
  return `
    <div class="card study-card" onclick="navigateTo('study/${study.id}'); router();">
      <div class="thumb-container">
        ${study.thumbnail_url
          ? `<img data-auth-src="${study.thumbnail_url}" alt="Thumbnail" class="auth-img"
                   onerror="this.parentElement.innerHTML='<div class=\\'thumb-placeholder\\'>🩻</div>'">`
          : '<div class="thumb-placeholder">🩻</div>'}
      </div>
      <div class="study-info">
        <div class="patient-name" style="font-size:1.05rem; font-weight:700;">${escapeHtml(study.patient_name) || 'Unknown Patient'}</div>
        <div class="study-meta">
          <span>${escapeHtml(study.patient_age) || '—'}</span>
          <span>•</span>
          <span>${escapeHtml(study.patient_sex) || '—'}</span>
          <span>•</span>
          <span class="badge badge-blue" style="padding:0.15rem 0.5rem;">${escapeHtml(study.modality) || '—'}</span>
          <span>•</span>
          <span>📁 ${study.num_files || 1} file(s)</span>
        </div>
        <div class="study-meta">
          <span>📅 ${formatDateTime(study.upload_date)}</span>
        </div>
      </div>
      <div class="study-footer">
        ${study.sent_to_orthanc
          ? '<span class="badge badge-green">✓ Orthanc</span>'
          : '<span class="badge badge-gray">Local only</span>'}
        <span class="btn btn-blue btn-sm">View →</span>
      </div>
    </div>
  `;
}

/**
 * Find all <img class="auth-img" data-auth-src="..."> elements inside a container
 * and load them with authenticated fetch.
 */
function loadAllAuthImages(container) {
  const imgs = container.querySelectorAll('img.auth-img[data-auth-src]');
  imgs.forEach(img => {
    const url = img.getAttribute('data-auth-src');
    if (url) loadAuthImage(img, url);
  });
}
