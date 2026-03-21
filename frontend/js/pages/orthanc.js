/**
 * pages/orthanc.js — Orthanc Browser Page with Credential Management
 */

async function renderOrthancPage(container) {
  container.innerHTML = `
    ${renderNavbar()}
    <div class="page-content">
      <div class="page-title">🖥️ Orthanc PACS Browser</div>

      <!-- Server Management Section -->
      <div class="card" style="margin-bottom: 1.5rem;">
        <div class="card-header">
          <h3>🔗 Orthanc Servers</h3>
          <button class="btn btn-purple btn-sm" id="btn-add-server" onclick="showAddServerModal()">
            ➕ Add Server
          </button>
        </div>
        <div class="card-body">
          <div id="servers-container">
            <div style="text-align:center; padding:1rem;">
              <div class="spinner spinner-dark" style="width:24px;height:24px;border-width:2px;margin:0 auto 0.5rem;"></div>
              <div class="text-muted text-sm">Loading servers…</div>
            </div>
          </div>
        </div>
      </div>

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

  // Load servers first, then health and studies
  await loadOrthancServers();
  checkOrthancHealth();
  loadOrthancStudies();
}

/* ── Server Management ─────────────────────────────────────────────────── */

async function loadOrthancServers() {
  const container = document.getElementById('servers-container');
  try {
    const servers = await apiGetOrthancServers();
    const user = getUser();
    const activeId = user?.last_orthanc_id;

    if (servers.length === 0) {
      container.innerHTML = `
        <div style="text-align:center; padding:1rem; color: var(--text-muted);">
          <p>No Orthanc servers configured. Click <strong>"Add Server"</strong> to add one.</p>
          <p class="text-sm" style="margin-top:0.5rem;">The system will use the default config until you add a server.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap:1rem;">
        ${servers.map(s => `
          <div class="server-card ${s.id === activeId ? 'active' : ''}" id="server-${s.id}">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
              <div>
                <div class="server-name">
                  ${escapeHtml(s.name)}
                  ${s.is_default ? '<span class="badge badge-purple" style="margin-left:0.5rem;">DEFAULT</span>' : ''}
                  ${s.id === activeId ? '<span class="badge badge-green" style="margin-left:0.25rem;">ACTIVE</span>' : ''}
                </div>
                <div class="server-url">${escapeHtml(s.url)}</div>
                <div class="text-sm text-muted" style="margin-top:0.25rem;">
                  User: ${escapeHtml(s.username) || '(none)'}
                </div>
              </div>
            </div>
            <div class="server-actions">
              <button class="btn btn-green btn-sm" onclick="testOrthancServer(${s.id})" title="Test Connection">
                🔌 Test
              </button>
              ${s.id !== activeId ? `
                <button class="btn btn-blue btn-sm" onclick="activateOrthancServer(${s.id})" title="Use this server">
                  ⚡ Use
                </button>
              ` : ''}
              <button class="btn btn-outline btn-sm" onclick="showEditServerModal(${s.id}, '${escapeHtml(s.name)}', '${escapeHtml(s.url)}', '${escapeHtml(s.username)}', '${escapeHtml(s.password)}', ${s.is_default})" title="Edit">
                ✏️
              </button>
              <button class="btn btn-red btn-sm" onclick="deleteOrthancServer(${s.id}, '${escapeHtml(s.name)}')" title="Delete">
                🗑️
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="text-muted">Error loading servers: ${escapeHtml(err.message)}</div>`;
  }
}

function showAddServerModal() {
  _showServerModal('Add Orthanc Server', {}, async (data) => {
    try {
      await apiCreateOrthancServer(data);
      showToast('Server added ✓', 'success');
      document.getElementById('server-modal')?.remove();
      await loadOrthancServers();
      // Refresh user data
      const user = await apiGetMe();
      setUser(user);
    } catch (err) {
      showToast(err.message, 'error');
    }
  });
}

function showEditServerModal(id, name, url, username, password, isDefault) {
  _showServerModal('Edit Orthanc Server', { name, url, username, password, is_default: isDefault }, async (data) => {
    try {
      await apiUpdateOrthancServer(id, data);
      showToast('Server updated ✓', 'success');
      document.getElementById('server-modal')?.remove();
      await loadOrthancServers();
    } catch (err) {
      showToast(err.message, 'error');
    }
  });
}

function _showServerModal(title, defaults, onSubmit) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = 'server-modal';
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:520px;">
      <h3>${title}</h3>
      <form id="server-form">
        <div class="form-group">
          <label>Server Name</label>
          <input type="text" class="form-control" id="srv-name" placeholder="e.g. CT Lab Orthanc" 
                 value="${escapeHtml(defaults.name || '')}" required>
        </div>
        <div class="form-group">
          <label>URL</label>
          <input type="text" class="form-control" id="srv-url" placeholder="http://192.168.1.10:8042"
                 value="${escapeHtml(defaults.url || '')}" required>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
          <div class="form-group">
            <label>Username</label>
            <input type="text" class="form-control" id="srv-username" placeholder="admin"
                   value="${escapeHtml(defaults.username || '')}">
          </div>
          <div class="form-group">
            <label>Password</label>
            <input type="password" class="form-control" id="srv-password" placeholder="password"
                   value="${escapeHtml(defaults.password || '')}">
          </div>
        </div>
        <div class="form-group" style="margin-bottom:0;">
          <label style="display:flex; align-items:center; gap:0.5rem; cursor:pointer;">
            <input type="checkbox" id="srv-default" ${defaults.is_default ? 'checked' : ''}>
            Set as default server
          </label>
        </div>
        <div class="modal-actions" style="margin-top:1.5rem;">
          <button type="button" class="btn btn-outline" onclick="document.getElementById('server-modal').remove()">
            Cancel
          </button>
          <button type="submit" class="btn btn-purple">
            💾 Save
          </button>
        </div>
      </form>
    </div>
  `;
  document.body.appendChild(overlay);

  document.getElementById('server-form').addEventListener('submit', (e) => {
    e.preventDefault();
    onSubmit({
      name      : document.getElementById('srv-name').value.trim(),
      url       : document.getElementById('srv-url').value.trim(),
      username  : document.getElementById('srv-username').value,
      password  : document.getElementById('srv-password').value,
      is_default: document.getElementById('srv-default').checked,
    });
  });
}

async function testOrthancServer(serverId) {
  showToast('Testing connection…', 'info');
  try {
    const result = await apiTestOrthancServer(serverId);
    if (result.success) {
      showToast(`✓ ${result.message} (v${result.version || '?'})`, 'success');
    } else {
      showToast(`✕ ${result.message}`, 'error');
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function activateOrthancServer(serverId) {
  try {
    await apiActivateOrthancServer(serverId);
    showToast('Server activated ✓', 'success');
    // Refresh user profile to get updated last_orthanc_id
    const user = await apiGetMe();
    setUser(user);
    await loadOrthancServers();
    // Refresh health and studies
    checkOrthancHealth();
    loadOrthancStudies();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function deleteOrthancServer(serverId, name) {
  if (!confirm(`Delete server "${name}"?`)) return;
  try {
    await apiDeleteOrthancServer(serverId);
    showToast('Server deleted', 'success');
    const user = await apiGetMe();
    setUser(user);
    await loadOrthancServers();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

/* ── Health check & Studies ────────────────────────────────────────────── */

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
