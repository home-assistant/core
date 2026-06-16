/* Willow sidebar panel. Self-contained web component, no external dependencies. */

const SENSOR_META = {
  temperature: { label: "Temperature", icon: "🌡️" },
  humidity: { label: "Humidity", icon: "♨" },
  moisture: { label: "Soil moisture", icon: "💦" },
  light: { label: "Light", icon: "💡" },
  illuminance: { label: "Illuminance", icon: "💡" },
  battery_life: { label: "Battery", icon: "🔋" },
  battery: { label: "Battery", icon: "🔋" },
  last_reading: { label: "Last reading", icon: "🕒" },
};

class WillowPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = undefined;
    this._lastSignature = "";
    this._renderedShell = false;
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  get hass() {
    return this._hass;
  }

  set narrow(value) {
    this._narrow = value;
  }

  connectedCallback() {
    this._renderShell();
    this._update();
  }

  _toggleMenu() {
    this.dispatchEvent(
      new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }),
    );
  }

  _willowDevices() {
    const hass = this._hass;
    if (!hass) {
      return [];
    }

    const entities = Object.values(hass.entities || {}).filter(
      (entry) => entry.platform === "willow",
    );

    const byDevice = new Map();
    for (const entry of entities) {
      const deviceId = entry.device_id || "_no_device";
      if (!byDevice.has(deviceId)) {
        byDevice.set(deviceId, []);
      }
      byDevice.get(deviceId).push(entry);
    }

    const devices = [];
    for (const [deviceId, deviceEntities] of byDevice.entries()) {
      const device = (hass.devices || {})[deviceId] || {};
      devices.push({
        id: deviceId,
        name: device.name_by_user || device.name || "Willow sensor",
        model: device.model || "",
        entities: deviceEntities,
      });
    }

    devices.sort((a, b) => a.name.localeCompare(b.name));
    return devices;
  }

  _signature(devices) {
    const hass = this._hass;
    return devices
      .map((device) =>
        device.entities
          .map((entry) => {
            const state = hass.states[entry.entity_id];
            return `${entry.entity_id}:${state ? state.state : "?"}`;
          })
          .join("|"),
      )
      .join("||");
  }

  _readingKey(entry) {
    const state = this._hass.states[entry.entity_id];
    const key =
      (state && state.attributes && state.attributes.translation_key) ||
      entry.translation_key ||
      "";
    if (key && SENSOR_META[key]) {
      return key;
    }
    const id = entry.entity_id.split(".")[1] || "";
    for (const metaKey of Object.keys(SENSOR_META)) {
      if (id.endsWith(metaKey)) {
        return metaKey;
      }
    }
    const deviceClass =
      state && state.attributes ? state.attributes.device_class : undefined;
    if (deviceClass && SENSOR_META[deviceClass]) {
      return deviceClass;
    }
    return "";
  }

  _formatState(entry) {
    const state = this._hass.states[entry.entity_id];
    if (!state) {
      return "—";
    }
    if (state.state === "unavailable" || state.state === "unknown") {
      return state.state;
    }
    const unit =
      state.attributes && state.attributes.unit_of_measurement
        ? ` ${state.attributes.unit_of_measurement}`
        : "";
    return `${state.state}${unit}`;
  }

  _formatLastReading(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }

    const diffMs = Date.now() - date.getTime();
    const absDiffMs = Math.abs(diffMs);
    const minuteMs = 60 * 1000;
    const hourMs = 60 * minuteMs;

    if (diffMs >= 0 && absDiffMs < hourMs) {
      const minutes = Math.max(1, Math.floor(absDiffMs / minuteMs));
      return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
    }

    if (diffMs >= 0 && absDiffMs < 24 * hourMs) {
      const hours = Math.floor(absDiffMs / hourMs);
      return `${hours} hour${hours === 1 ? "" : "s"} ago`;
    }

    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  }

  _formatReading(entry) {
    const state = this._hass.states[entry.entity_id];
    if (!state || state.state === "unavailable" || state.state === "unknown") {
      return this._formatState(entry);
    }
    if (this._readingKey(entry) === "last_reading") {
      return this._formatLastReading(state.state);
    }
    return this._formatState(entry);
  }

  _renderShell() {
    if (this._renderedShell) {
      return;
    }
    this._renderedShell = true;
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          height: 100%;
          background: var(--primary-background-color, #fafafa);
          color: var(--primary-text-color, #212121);
        }
        .toolbar {
          display: flex;
          align-items: center;
          height: var(--header-height, 56px);
          padding: 0 16px;
          background: var(--app-header-background-color, var(--primary-color, #03a9f4));
          color: var(--app-header-text-color, #fff);
          font-size: 20px;
          font-weight: 400;
          box-sizing: border-box;
        }
        .menu-button {
          background: none;
          border: none;
          color: inherit;
          cursor: pointer;
          margin-right: 16px;
          padding: 8px;
          border-radius: 50%;
          line-height: 0;
        }
        .menu-button:hover { background: rgba(255, 255, 255, 0.1); }
        .menu-button svg { width: 24px; height: 24px; fill: currentColor; }
        .content { padding: 16px; max-width: 1200px; margin: 0 auto; }
        .grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 16px;
        }
        .card {
          background: var(--card-background-color, #fff);
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0, 0, 0, 0.1));
          padding: 16px;
          box-sizing: border-box;
        }
        .card h2 {
          margin: 0 0 4px;
          font-size: 18px;
          font-weight: 500;
        }
        .card .model {
          margin: 0 0 12px;
          font-size: 13px;
          color: var(--secondary-text-color, #727272);
        }
        .reading {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 6px 0;
          border-top: 1px solid var(--divider-color, #e0e0e0);
        }
        .reading .label { display: flex; align-items: center; gap: 8px; }
        .reading .value { font-weight: 500; }
        .empty {
          text-align: center;
          padding: 48px 16px;
          color: var(--secondary-text-color, #727272);
        }
      </style>
      <div class="toolbar">
        <button class="menu-button" title="Menu">
          <svg viewBox="0 0 24 24"><path d="M3 6h18v2H3V6m0 5h18v2H3v-2m0 5h18v2H3v-2Z"/></svg>
        </button>
        <span>Willow</span>
      </div>
      <div class="content"><div class="grid" id="grid"></div></div>
    `;
    this.shadowRoot
      .querySelector(".menu-button")
      .addEventListener("click", () => this._toggleMenu());
  }

  _update() {
    if (!this._hass || !this._renderedShell) {
      return;
    }

    const devices = this._willowDevices();
    const signature = this._signature(devices);
    if (signature === this._lastSignature) {
      return;
    }
    this._lastSignature = signature;

    const grid = this.shadowRoot.getElementById("grid");
    grid.innerHTML = "";

    if (!devices.length) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent =
        "No Willow sensors found yet. Once your Willow devices report data they will appear here.";
      grid.appendChild(empty);
      return;
    }

    for (const device of devices) {
      const card = document.createElement("div");
      card.className = "card";

      const h2 = document.createElement("h2");
      h2.textContent = device.name;
      card.appendChild(h2);

      if (device.model) {
        const model = document.createElement("p");
        model.className = "model";
        model.textContent = device.model;
        card.appendChild(model);
      }

      for (const entry of device.entities) {
        const key = this._readingKey(entry);
        const meta = SENSOR_META[key] || { label: null, icon: "•" };
        const state = this._hass.states[entry.entity_id];
        const label =
          meta.label ||
          (state && state.attributes && state.attributes.friendly_name) ||
          entry.entity_id;

        const reading = document.createElement("div");
        reading.className = "reading";

        const labelSpan = document.createElement("span");
        labelSpan.className = "label";
        labelSpan.textContent = `${meta.icon} ${label}`;

        const valueSpan = document.createElement("span");
        valueSpan.className = "value";
        valueSpan.textContent = this._formatReading(entry);

        reading.appendChild(labelSpan);
        reading.appendChild(valueSpan);
        card.appendChild(reading);
      }

      grid.appendChild(card);
    }
  }
}

customElements.define("willow-panel", WillowPanel);
