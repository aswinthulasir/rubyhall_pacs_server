/**
 * pages/login.js — Login Page
 */

function renderLoginPage(container) {
  container.innerHTML = `
    <div class="auth-wrapper">
      <div class="auth-card">
        <div class="logo">
          <div class="icon">🏥</div>
          <h1>Hospital PACS</h1>
          <p>Picture Archiving & Communication System</p>
        </div>
        <h2>Sign In</h2>
        <form id="login-form">
          <div class="form-group">
            <label for="login-username">Username</label>
            <input type="text" class="form-control" id="login-username"
                   placeholder="Enter your username" required autocomplete="username">
          </div>
          <div class="form-group">
            <label for="login-password">Password</label>
            <input type="password" class="form-control" id="login-password"
                   placeholder="Enter your password" required autocomplete="current-password">
          </div>
          <button type="submit" class="btn btn-blue btn-block btn-lg" id="btn-login">
            🔵 Sign In
          </button>
        </form>
        <p style="text-align:center; margin-top:1.25rem; color: var(--text-secondary); font-size: 0.9rem;">
          Don't have an account?
          <a href="#register" style="font-weight:600;">Create one</a>
        </p>
      </div>
    </div>
  `;

  document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('btn-login');
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Signing in…';

    try {
      await apiLogin(username, password);
      // Fetch user profile
      const user = await apiGetMe();
      setUser(user);
      showToast(`Welcome back, ${user.full_name}!`, 'success');
      navigateTo('dashboard');
      router();
    } catch (err) {
      showToast(err.message, 'error');
      btn.disabled = false;
      btn.innerHTML = '🔵 Sign In';
    }
  });
}
