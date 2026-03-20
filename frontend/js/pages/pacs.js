/**
 * pages/pacs.js — Show PACS Page
 * Lists ALL uploaded studies from ALL users
 */

async function renderPacsPage(container) {
  container.innerHTML = `
    ${renderNavbar()}
    <div class="page-content">
      <div class="page-title">🏥 PACS — All Studies</div>
      <div id="pacs-container">
        <div style="text-align:center; padding: 2rem;">
          <div class="spinner spinner-dark" style="width:32px;height:32px;border-width:3px;margin: 0 auto 0.75rem;"></div>
          <div class="text-muted">Loading all PACS studies…</div>
        </div>
      </div>
    </div>
  `;

  await loadAllPacsStudies();
}

async function loadAllPacsStudies() {
  const container = document.getElementById('pacs-container');
  try {
    const studies = await apiGetAllStudies();
    if (studies.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📭</div>
          <h4>No Studies in PACS</h4>
          <p>No studies have been uploaded yet.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="text-muted" style="margin-bottom:1rem; font-size:0.9rem;">
        Showing <strong>${studies.length}</strong> study/studies from all users
      </div>
      <div class="study-grid">
        ${studies.map(s => renderPacsStudyCard(s)).join('')}
      </div>
    `;

    // Load authenticated images
    loadAllAuthImages(container);

  } catch (err) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚠️</div>
        <h4>Error</h4>
        <p>${escapeHtml(err.message)}</p>
      </div>
    `;
  }
}

function renderPacsStudyCard(study) {
  const pdfSection = study.pdf_reports && study.pdf_reports.length > 0
    ? `<div style="margin-top:0.5rem; padding-top:0.5rem; border-top:1px solid var(--border-color);">
         <div style="font-size:0.82rem; font-weight:600; margin-bottom:0.25rem;">📄 PDF Reports (${study.pdf_reports.length})</div>
         ${study.pdf_reports.map(r => `
           <div style="font-size:0.8rem; color: var(--text-muted);">
             📄 ${escapeHtml(r.file_name) || 'report.pdf'}
             ${r.notes ? ` — <em>${escapeHtml(r.notes)}</em>` : ''}
           </div>
         `).join('')}
       </div>`
    : '';

  return `
    <a href="#study/${study.id}" class="study-card">
      <div class="study-card-thumb">
        ${study.thumbnail_url
          ? `<img data-auth-src="${study.thumbnail_url}" alt="Thumb" class="auth-img"
                   onerror="this.parentElement.innerHTML='<div class=\\'thumb-placeholder\\'>🩻</div>'">`
          : '<div class="thumb-placeholder">🩻</div>'}
      </div>
      <div class="study-card-info">
        <div class="study-card-name">${escapeHtml(study.patient_name) || 'Unknown Patient'}</div>
        <div class="study-card-meta">
          <span class="badge badge-blue">${escapeHtml(study.modality) || '—'}</span>
          <span>MR: <strong>${escapeHtml(study.mr_number)}</strong></span>
        </div>
        <div class="study-card-meta">
          <span>📁 ${study.num_files || 1} file(s)</span>
          <span>${formatFileSize(study.file_size_kb)}</span>
        </div>
        <div class="study-card-meta" style="margin-top:0.25rem;">
          <span>📅 ${formatDateTime(study.upload_date)}</span>
        </div>
        <div class="study-card-meta" style="margin-top:0.25rem; color: var(--blue);">
          <span>👤 Uploaded by: <strong>${escapeHtml(study.uploader_name) || 'Unknown'}</strong></span>
        </div>
        <div style="margin-top:0.35rem;">
          ${study.sent_to_orthanc
            ? '<span class="badge badge-green">✓ Sent to Orthanc</span>'
            : '<span class="badge badge-gray">Not sent</span>'}
          <span class="badge ${study.status === 'CONFIRMED' ? 'badge-green' : 'badge-yellow'}">${study.status}</span>
        </div>
        ${pdfSection}
      </div>
    </a>
  `;
}
