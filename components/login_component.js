
class LoginComponent {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.onLoginSuccess = options.onLoginSuccess || (() => { });
        this.onLoginFail = options.onLoginFail || (() => { });
        this.onLogout = options.onLogout || (() => { });
        this.apiEndpoint = options.apiEndpoint || '/api/user-aggregate/token';
        this.envList = options.envList || ["QA1", "QA2", "QA3", "QA4", "QA5", "QA6", "QA7", "QA8", "Prod"];
        this.initialState = options.initialState || null;

        this.render();
        this.attachEvents();

        if (this.initialState) {
            this.restoreSession(this.initialState);
        }
    }

    restoreSession(state) {
        // 0. HARDENED CHECK: If no token, logout immediately.
        if (!state || !state.access_token) {
            console.warn("Restore Session: No access token found. Logging out.");
            this.onLogout();
            return;
        }

        // Validate Token Expiry
        if (state && state.access_token) {
            try {
                let base64Url = state.access_token.split('.')[1];
                let base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                let jsonPayload = decodeURIComponent(atob(base64).split('').map(function (c) {
                    return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
                }).join(''));

                const payload = JSON.parse(jsonPayload);
                const exp = payload.exp * 1000; // to ms
                const now = Date.now();

                if (now > exp) {
                    console.warn("Session expired. Clearing.");
                    this.onLogout();
                    return;
                }
            } catch (e) {
                console.error("Token validation failed. Forcing logout.", e);
                this.onLogout();
                return;
            }
        }

        const formView = this.container.querySelector('#lc-view-form');
        const successView = this.container.querySelector('#lc-view-logged-in');

        // Update UI
        if (formView) formView.style.display = 'none';
        if (successView) {
            successView.style.display = 'block';
            this.container.querySelector('#lc-display-user').innerText = state.username || 'User';
            this.container.querySelector('#lc-display-env').innerText = state.environment ? `${state.environment} (${state.tenant || ''})` : 'Restored Session';
        }
    }

    render() {
        if (!this.container) return;

        // Initial View: Form
        this.container.innerHTML = `
            <div id="lc-view-form" class="login-component-wrapper">
                <div class="lc-row">
                    <div class="lc-form-group">
                        <label>Environment</label>
                        <div class="lc-custom-dropdown" id="lc-env-dropdown">
                            <div class="lc-dropdown-display" id="lc-env-display">Select Environment</div>
                            <input type="hidden" id="lc-env-input">
                            <div class="lc-dropdown-menu">
                                <ul class="lc-dropdown-list">
                                    ${this.envList.map(env => `<li class="lc-dropdown-item" data-value="${env}">${env}</li>`).join('')}
                                </ul>
                            </div>
                        </div>
                    </div>
                    <div class="lc-form-group">
                        <label>Tenant</label>
                        <input type="text" id="lc-tenant" class="lc-input" placeholder="e.g. sf_plus_qazone2">
                    </div>
                </div>
                <div class="lc-row">
                    <div class="lc-form-group">
                        <label>Username</label>
                        <input type="text" id="lc-username" class="lc-input">
                    </div>
                    <div class="lc-form-group">
                        <label>Password</label>
                        <input type="password" id="lc-password" class="lc-input">
                    </div>
                </div>
                <button id="lc-login-btn" class="lc-btn">Login</button>
                <div id="lc-error" class="lc-error hidden"></div>
            </div>

            <div id="lc-view-logged-in" class="login-component-wrapper" style="display:none; text-align: center;">
                 <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid #10b981; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
                    <div style="font-size: 1.2rem; color: #10b981; font-weight: bold; margin-bottom: 0.5rem;">
                         Logged In Successfully ✅
                    </div>
                     <div style="color: #cbd5e1; font-size: 0.9rem; margin-bottom: 0.2rem;">
                        Environment: <strong id="lc-display-env" style="color: #6ee7b7;">-</strong>
                    </div>
                    <div style="color: #cbd5e1; font-size: 0.9rem;">
                        User: <strong id="lc-display-user" style="color: #fca5a5;">-</strong>
                    </div>
                 </div>
                 <button id="lc-logout-btn" class="lc-btn" style="background: #ef4444;">Logout / Switch Account</button>
            </div>
        `;
    }

    attachEvents() {
        const display = this.container.querySelector('#lc-env-display');
        const menu = this.container.querySelector('.lc-dropdown-menu');
        const input = this.container.querySelector('#lc-env-input');
        const list = this.container.querySelector('.lc-dropdown-list');

        // Dropdown Logic
        display.addEventListener('click', (e) => {
            e.stopPropagation();
            menu.classList.toggle('show');
        });

        list.addEventListener('click', (e) => {
            if (e.target.classList.contains('lc-dropdown-item')) {
                const val = e.target.getAttribute('data-value');
                display.textContent = e.target.textContent;
                input.value = val;
                menu.classList.remove('show');
            }
        });

        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) {
                menu.classList.remove('show');
            }
        });

        // Login Logic
        const btn = this.container.querySelector('#lc-login-btn');
        const logoutBtn = this.container.querySelector('#lc-logout-btn');
        const inputs = this.container.querySelectorAll('input');

        const doLogin = async () => {
            const env = input.value;
            const tenant = this.container.querySelector('#lc-tenant').value.trim();
            const username = this.container.querySelector('#lc-username').value.trim();
            const password = this.container.querySelector('#lc-password').value;
            const errorDiv = this.container.querySelector('#lc-error');

            if (!env || !tenant || !username || !password) {
                errorDiv.textContent = "Please fill all fields.";
                errorDiv.classList.remove('hidden');
                return;
            }

            btn.disabled = true;
            btn.textContent = "Logging in...";
            errorDiv.classList.add('hidden');

            try {
                const res = await fetch(this.apiEndpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ environment: env, tenant, username, password })
                });
                const data = await res.json();

                if (data.access_token) {
                    this.onLoginSuccess(data.access_token, { environment: env, tenant, username });

                    // Switch to Logged In View
                    document.getElementById('lc-view-form').style.display = 'none';
                    document.getElementById('lc-view-logged-in').style.display = 'block';

                    document.getElementById('lc-display-user').innerText = username;
                    document.getElementById('lc-display-env').innerText = `${env} (${tenant})`;

                    btn.textContent = "Login"; // Reset for next time
                    btn.disabled = false;

                } else {
                    throw new Error(data.error || "Login Failed");
                }
            } catch (err) {
                this.onLoginFail(err); // Trigger fail callback
                errorDiv.textContent = err.message;
                errorDiv.classList.remove('hidden');
                btn.disabled = false;
                btn.textContent = "Login";
            }
        };

        const doLogout = () => {
            // Reset View
            document.getElementById('lc-view-logged-in').style.display = 'none';
            document.getElementById('lc-view-form').style.display = 'block';

            // Custom Logout Handler
            this.onLogout();
        };

        btn.addEventListener('click', doLogin);
        logoutBtn.addEventListener('click', doLogout);

        // Enter Key Support
        inputs.forEach(inp => {
            inp.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') doLogin();
            });
        });
    }

    setEnvironment(envName, isLocked = false) {
        const display = this.container.querySelector('#lc-env-display');
        const input = this.container.querySelector('#lc-env-input');
        const dropdown = this.container.querySelector('#lc-env-dropdown');

        if (!display || !input) return;

        if (envName) {
            display.textContent = envName;
            input.value = envName;
        }

        if (isLocked) {
            display.classList.add('disabled');
            display.style.pointerEvents = 'none';
            display.style.opacity = '0.7';
            display.style.backgroundColor = '#f1f3f4';
            dropdown.classList.add('locked'); // optional marker
        } else {
            display.classList.remove('disabled');
            display.style.pointerEvents = 'auto';
            display.style.opacity = '1';
            display.style.backgroundColor = 'transparent';
            dropdown.classList.remove('locked');
            // If unlocking, maybe reset to "Select Environment" if value is forced? 
            // Better to leave it as is or let user change it.
        }
    }
}
