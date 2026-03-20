/**
 * pages/orthanc.js — Orthanc Browser Page
 */

async function renderOrthancPage(container) {
  container.innerHTML = `
    ${renderNavbar()}
    <div class="page-content">
      <div class="page-title">🖥️ Orthanc PACS Browser</div>

      <!-- Health Badge -->
      <div class="card" style="margin-bottom: 1.5rem;">
        <div class="card-body" style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;">
          <div class="status-indicator" id="orthanc-status">
            <div class="spinner spinner-dark" style="width:16px;height:16px;border-width:2px;"></div>
            <span class="text-muted">Checking Orthanc status…</span>
          </div>
          <button class="btn btn-blue btn-sm" id="btn-refresh-orthanc" onclick="refreshOrthancPage()">
            🔄 Refresh
          </button>
        </div>
      </div>

      <!-- Studies Table -->
      <div class="card">
        <div class="card-header">
          <h3>📋 Studies in Orthanc</h3>
        </div>
        <div id="orthanc-studies-container" style="overflow-x: auto;">
          <div style="text-align:center; padding:2rem;">
            <div class="spinner spinner-dark" style="width:32px;height:32px;border-width:3px;margin:0 auto 0.75rem;"></div>
            <div class="text-muted">Loading Orthanc studies…</div>
          </div>
        </div>
      </div>
    </div>
  `;

  // Check health
  checkOrthancHealth();
  // Load studies
  loadOrthancStudies();
}

async function checkOrthancHealth() {
  const statusEl = document.getElementById('orthanc-status');
  try {
    const info = await apiOrthancHealth();
    statusEl.innerHTML = `
      <span class="status-dot online"></span>
      <span style="font-weight:600; color: var(--green);">Online</span>
      <span class="text-muted text-sm" style="margin-left: 0.5rem;">
        Version: ${escapeHtml(info.version || '—')}
      </span>
    `;
  } catch {
    statusEl.innerHTML = `
      <span class="status-dot offline"></span>
      <span style="font-weight:600; color: var(--red);">Offline</span>
      <span class="text-muted text-sm" style="margin-left: 0.5rem;">
        Could not reach Orthanc
      </span>
    `;
  }
}

async function loadOrthancStudies() {
  const container = document.getElementById('orthanc-studies-container');
  try {
    const studies = await apiGetOrthancStudies();

    if (studies.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📭</div>
          <h4>No Studies in Orthanc</h4>
          <p>Send studies from your dashboard to populate this list.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <table class="table-modern">
        <thead>
          <tr>
            <th>Patient Name</th>
            <th>Patient ID</th>
            <th>Study Date</th>
            <th>Modality</th>
            <th>Description</th>
            <th>Orthanc ID</th>
          </tr>
        </thead>
        <tbody>
          ${studies.map(s => `
            <tr>
              <td style="font-weight:600;">${escapeHtml(s.patient_name) || '—'}</td>
              <td>${escapeHtml(s.patient_id) || '—'}</td>
              <td>${formatDate(s.study_date)}</td>
              <td><span class="badge badge-blue">${escapeHtml(s.modality) || '—'}</span></td>
              <td>${escapeHtml(s.study_description) || '—'}</td>
              <td class="text-sm text-muted" style="font-family:monospace; word-break:break-all;">${escapeHtml(s.orthanc_id) || '—'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (err) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚠️</div>
        <h4>Error Loading Orthanc</h4>
        <p>${escapeHtml(err.message)}</p>
      </div>
    `;
  }
}

function refreshOrthancPage() {
  renderOrthancPage(document.getElementById('app'));
}
