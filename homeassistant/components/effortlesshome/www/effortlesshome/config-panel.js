class ConfigPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (this.parentNode) {
      this.populateCurrentUser();
    }
  }

  get hass() {
    return this._hass;
  }

  async connectedCallback() {
    this.innerHTML = `
      <style>
        :host {
          display: block;
          min-height: 100vh;
          background-color: var(--lovelace-background, var(--primary-background-color));
          color: var(--primary-text-color);
          font-family: var(--paper-font-body1_-_font-family, "Arial", sans-serif);
          transition: background-color 0.3s, color 0.3s;
          padding: 20px;
        }

        .dashboard-container {
          max-width: 1000px;
          margin: 0 auto;
          display: flex;
          flex-direction: column;
          gap: 24px;
        }

        .brand-logo {
          position: absolute;
          top: 0;
          right: 0;
        }

        .brand-logo img {
          max-width: 40px;
          height: auto;
          transition: opacity 0.2s;
        }

        .brand-logo img:hover {
          opacity: 0.8;
        }

        .header-section {
          display: flex;
          flex-wrap: wrap;
          gap: 24px;
          background: var(--card-background-color);
          padding: 24px;
          border-radius: 16px;
          box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0,0,0,0.1));
        }

        .profile-info {
          flex: 1;
          min-width: 250px;
          text-align: center;
          border-right: 1px solid var(--divider-color);
          padding-right: 24px;
        }

        @media (max-width: 600px) {
          .profile-info {
            border-right: none;
            border-bottom: 1px solid var(--divider-color);
            padding-right: 0;
            padding-bottom: 24px;
          }
        }

        .profile-info img {
          width: 80px;
          height: 80px;
          border-radius: 50%;
          margin-bottom: 12px;
          border: 2px solid var(--primary-color);
          background: var(--secondary-background-color);
        }

        .profile-info h2 {
          margin: 8px 0;
          font-size: 1.5rem;
        }

        .profile-info p {
          color: var(--secondary-text-color);
          font-size: 0.9rem;
          margin-bottom: 16px;
        }

        .controls {
          display: flex;
          justify-content: center;
          gap: 12px;
          margin-bottom: 16px;
        }

        .btn {
          padding: 8px 16px;
          border-radius: 8px;
          border: none;
          cursor: pointer;
          font-weight: 500;
          transition: opacity 0.2s, transform 0.1s;
        }

        .btn:active { transform: scale(0.98); }

        .btn-primary { background: var(--primary-color); color: white; }
        .btn-outline { background: transparent; border: 1px solid var(--primary-color); color: var(--primary-color); }

        .system-status {
          flex: 2;
          min-width: 300px;
          display: flex;
          flex-direction: column;
          gap: 16px;
          position: relative;
        }

        .status-grid {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .status-item {
          padding: 12px 0;
          border-bottom: 1px solid var(--divider-color);
        }

        .status-item:last-child {
          border-bottom: none;
        }

        .status-item h4 { margin: 0 0 4px 0; color: var(--secondary-text-color); font-size: 0.8rem; text-transform: uppercase; }

        .status-item a {
          color: var(--primary-color);
          text-decoration: none;
          font-weight: 500;
          transition: color 0.2s;
        }

        .status-item a:hover {
          color: var(--accent-color);
          text-decoration: underline;
        }

        .nav-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 20px;
        }

        .tile {
          background-color: var(--card-background-color);
          border-radius: 12px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 32px;
          text-align: center;
          font-weight: bold;
          text-decoration: none;
          color: var(--primary-text-color);
          box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,0.1));
          transition: background-color 0.3s, box-shadow 0.3s, transform 0.2s;
        }

        .tile:hover {
          background-color: var(--secondary-background-color);
          box-shadow: var(--ha-card-box-shadow-hover, 0 4px 8px rgba(0,0,0,0.15));
          transform: translateY(-2px);
        }

        .tile ha-icon {
          --mdc-icon-size: 40px;
          margin-bottom: 12px;
          color: var(--orange);
        }

        .footer-links {
          text-align: center;
          padding: 20px;
          color: var(--secondary-text-color);
        }

        .footer-links a {
          color: var(--primary-color);
          text-decoration: none;
          margin: 0 12px;
        }

        /* Matter Section Styles */
        .matter-section {
          background: var(--card-background-color);
          padding: 24px;
          border-radius: 16px;
          box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0,0,0,0.1));
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .matter-section h2 {
          margin: 0 0 8px 0;
          font-size: 1.25rem;
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .matter-section h2 ha-icon {
          color: var(--primary-color);
        }

        .bridge-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 20px;
        }

        .bridge-card {
          background: var(--secondary-background-color);
          padding: 20px;
          border-radius: 12px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          border: 1px solid var(--divider-color);
        }

        .bridge-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .bridge-header h3 { margin: 0; font-size: 1.1rem; }

        .status-badge {
          padding: 4px 8px;
          border-radius: 12px;
          font-size: 0.75rem;
          font-weight: bold;
          text-transform: uppercase;
        }

        .status-running { background: var(--success-color, #4caf50); color: white; }
        .status-stopped { background: var(--error-color, #f44336); color: white; }

        .pairing-info {
          background: var(--card-background-color);
          padding: 12px;
          border-radius: 8px;
          font-family: monospace;
          font-size: 0.9rem;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .pairing-info span { color: var(--secondary-text-color); font-size: 0.75rem; }
        .pairing-code { font-weight: bold; letter-spacing: 1px; color: var(--primary-color); }
      </style>

      <div class="dashboard-container">
        <div class="header-section">
          <div class="profile-info">
            <div id="current-user">
              <img src="/local/effortlesshome/user.png" alt="Profile">
              <h2 id="user-name">Loading...</h2>
              <p id="ha-url">Connecting...</p>
            </div>
            <div class="controls">
              <button id="logout-btn" class="btn btn-outline">Logout</button>
              <button id="restart-btn" class="btn btn-primary">Restart</button>
            </div>
          </div>

          <div class="system-status">
             <div class="brand-logo">
               <a href="https://www.effortlesshome.co" target="_blank">
                 <img src="/local/effortlesshome/ehlogo.jpg" alt="EH Logo">
               </a>
             </div>
             <div class="status-grid">
                <div class="status-item">
                  <h4>Security</h4>
                  <a href="/profile/security">Two-Factor Authentication</a>
                </div>
                <div class="status-item">
                  <h4>Account</h4>
                  <a href="https://my.effortlesshome.co" target="_blank">Manage Subscription</a>
                </div>
             </div>
          </div>
        </div>

        <div class="nav-grid">
          ${this._tile("/effortlesshome-area-panel", "mdi:label-multiple", "Set Device Areas")}
          ${this._tile("/effortlesshome-label-panel", "mdi:label", "Set Labels")}
        </div>

        <div id="matter-section" class="matter-section">
          <h2><ha-icon icon="mdi:hub"></ha-icon> Matter Bridges</h2>
          <div id="bridge-list" class="bridge-grid">
             <p>Loading Matter bridges...</p>
          </div>
        </div>

        <div class="footer-links">
           <a href="https://effortlesshome.co" target="_blank">effortlesshome.co</a> |
           <a href="https://effortlesshome.co/support" target="_blank">Support</a>
        </div>
      </div>
    `;

    this.querySelector("#logout-btn")?.addEventListener("click", () => this.handleLogout());
    this.querySelector("#restart-btn")?.addEventListener("click", () => this.handleRestart());

    this.populateCurrentUser();
    this.fetchMatterBridges();
  }

  async handleLogout() {
    if (!this.hass) return;
    try {
      await this.hass.auth.revoke();
      if (window.localStorage) window.localStorage.clear();
      document.location.href = "/";
    } catch (err) {
      console.error(err);
      alert("Logout failed");
    }
  }

  async handleRestart() {
    if (!this.hass) return;
    if (!confirm("Are you sure you want to restart Home Assistant?")) return;
    try {
      await this.hass.callService("homeassistant", "restart");
      alert("Restarting System...");
    } catch (err) {
      console.error(err);
      alert("Restart failed.");
    }
  }

  populateCurrentUser() {
    if (!this.hass) return;
    const nameEl = this.querySelector("#user-name");
    const urlEl = this.querySelector("#ha-url");
    if (nameEl) nameEl.textContent = this.hass.user.name;
    if (urlEl) urlEl.textContent = this.hass.states["sensor.ha_url"]?.state || "Connected";

    if (!this.hass.user.is_admin) {
      const restartBtn = this.querySelector("#restart-btn");
      if (restartBtn) restartBtn.style.display = "none";
    }
  }

  _tile(href, icon, label) {
    return `
      <a href="${href}" class="tile">
        <ha-icon icon="${icon}"></ha-icon>
        ${label}
      </a>
    `;
  }

  async fetchMatterBridges() {
    const hostname = window.location.hostname;
    const url = `http://${hostname}:8482/api/matter/bridges`;
    const list = this.querySelector("#bridge-list");

    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error("Matter Hub unreachable");
      const bridges = await response.json();

      if (bridges && bridges.length > 0) {
        if (list) list.innerHTML = bridges.map(b => this._renderBridgeCard(b)).join("");
      } else {
        if (list) list.innerHTML = "<p>No Matter bridges found.</p>";
      }
    } catch (err) {
      console.error("Failed to fetch Matter bridges:", err);
      if (list) list.innerHTML = "<p style='color: var(--error-color, #f44336);'>Matter Hub unreachable or API failed.</p>";
    }
  }

  _renderBridgeCard(bridge) {
    const comm = bridge.commissioning || {};
    const info = bridge.basicInformation || {};

    // Generate a unique id for the factory reset button
    const resetBtnId = `factory-reset-btn-${bridge.id}`;

    // Attach the event listener after rendering
    setTimeout(() => {
      const btn = this.querySelector(`#${resetBtnId}`);
      if (btn) {
        btn.onclick = async () => {
          if (!confirm("Factory reset this bridge? This cannot be undone.")) return;
          btn.disabled = true;
          btn.textContent = "Resetting...";
          try {
            const hostname = window.location.hostname;
            const url = `http://${hostname}:8482/api/matter/bridges/${bridge.id}/actions/factory-reset`;
            const resp = await fetch(url, { method: "GET" });
            if (!resp.ok) throw new Error("Factory reset failed");
            alert("Bridge factory reset successfully.");
          } catch (err) {
            alert("Factory reset failed: " + (err.message || err));
          } finally {
            btn.disabled = false;
            btn.textContent = "Factory Reset";
          }
        };
      }
    }, 0);

    return `
      <div class="bridge-card">
        <div class="bridge-header">
          <h3>${bridge.name || "Matter Bridge"}</h3>
          <span class="status-badge status-${bridge.status === "running" ? "running" : "stopped"}">
            ${bridge.status}
          </span>
        </div>
        
        <div class="pairing-info">
          <span>Manual Pairing Code</span>
          <div class="pairing-code">${comm.manualPairingCode || "N/A"}</div>
          
          <div style="margin-top: 8px;">
            <span>Passcode: <strong>${comm.passcode || "N/A"}</strong></span>
            <span style="margin-left: 12px;">Discriminator: <strong>${comm.discriminator || "N/A"}</strong></span>
          </div>
        </div>

        <div style="font-size: 0.85rem; color: var(--secondary-text-color);">
           Devices: <strong>${bridge.deviceCount || 0}</strong><br>
           Vendor: ${info.vendorName || "Unknown"} | Version: ${info.softwareVersion || "N/A"}
        </div>

        <button id="${resetBtnId}" class="btn btn-outline" style="margin-top:10px;align-self:flex-start;">Factory Reset</button>
      </div>
    `;
  }
}

customElements.define("effortlesshome-config-panel", ConfigPanel);
