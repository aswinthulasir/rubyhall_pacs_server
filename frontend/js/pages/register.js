/**
 * pages/register.js — Registration Page
 */

async function renderRegisterPage(container) {
  container.innerHTML = `
    <div class="auth-wrapper">
      <div class="auth-card" style="max-width:480px;">
        <div class="logo">
          <div class="icon">🏥</div>
          <h1>Hospital PACS</h1>
          <p>Create a New Account</p>
        </div>
        <form id="register-form">
          <div class="form-group">
            <label for="reg-fullname">Full Name</label>
            <input type="text" class="form-control" id="reg-fullname"
                   placeholder="Dr. John Doe" required>
          </div>
          <div class="form-group">
            <label for="reg-username">Username</label>
            <input type="text" class="form-control" id="reg-username"
                   placeholder="johndoe" required>
          </div>
          <div class="form-group">
            <label for="reg-email">Email</label>
            <input type="email" class="form-control" id="reg-email"
                   placeholder="john@hospital.com" required>
          </div>
          <div class="form-group">
            <label for="reg-password">Password</label>
            <input type="password" class="form-control" id="reg-password"
                   placeholder="Min 6 characters" required minlength="6">
          </div>
          <div class="form-group">
            <label for="reg-role">Role</label>
            <select class="form-control" id="reg-role">
              <option value="">Loading roles…</option>
            </select>
          </div>
          <button type="submit" class="btn btn-green btn-block btn-lg" id="btn-register">
            🟢 Register
          </button>
        </form>
        <p style="text-align:center; margin-top:1.25rem; color: var(--text-secondary); font-size: 0.9rem;">
          Already have an account?
          <a href="#login" style="font-weight:600;">Sign In</a>
        </p>
      </div>
    </div>
  `;

  // Load roles
  try {
    const roles = await apiGetRoles();
    const select = document.getElementById('reg-role');
    select.innerHTML = roles.map(r =>
      `<option value="${r.id}" ${r.id === 4 ? 'selected' : ''}>${r.name.charAt(0).toUpperCase() + r.name.slice(1).replace('_', ' ')}</option>`
    ).join('');
  } catch {
    showToast('Could not load roles', 'error');
  }

  document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('btn-register');

    const payload = {
      full_name: document.getElementById('reg-fullname').value.trim(),
      username: document.getElementById('reg-username').value.trim(),
      email: document.getElementById('reg-email').value.trim(),
      password: document.getElementById('reg-password').value,
      role_id: parseInt(document.getElementById('reg-role').value),
    };

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Creating account…';

    try {
      await apiRegister(payload);
      showToast('Account created! Please sign in.', 'success');
      navigateTo('login');
      router();
    } catch (err) {
      showToast(err.message, 'error');
      btn.disabled = false;
      btn.innerHTML = '🟢 Register';
    }
  });
}
