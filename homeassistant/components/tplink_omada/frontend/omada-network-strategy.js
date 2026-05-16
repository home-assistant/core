/**
 * Omada Network Dashboard Strategy
 * Single-page layout: device table + client panel (search / filter / enable)
 *
 * One view, two live custom-card tables — no tab navigation.
 *
 * Custom elements (strategies):
 *   ll-strategy-dashboard-omada-network
 *
 * Custom elements (cards):
 *   omada-devices-table-card   (type: custom:omada-devices-table-card)
 *   omada-clients-panel-card   (type: custom:omada-clients-panel-card)
 *
 * Strategy type: custom:omada-network
 */

// ---------------------------------------------------------------------------
// Translation keys used by Omada entities
// ---------------------------------------------------------------------------

const TK = {
  STATUS: "device_status",
  CPU: "cpu_usage",
  MEM: "mem_usage",
  WAN_LINK: "wan_link",
  POE_CONTROL: "poe_control",
  WAN_V4: "wan_connect_ipv4",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function escHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function _macFromUniqueId(unique_id) {
  if (!unique_id) return null;
  const m = unique_id.match(
    /([0-9a-f]{2}[:\-][0-9a-f]{2}[:\-][0-9a-f]{2}[:\-][0-9a-f]{2}[:\-][0-9a-f]{2}[:\-][0-9a-f]{2})$/i,
  );
  return m ? m[1] : null;
}

function classifyDevice(entities) {
  const keys = new Set(entities.map((e) => e.translation_key));
  if (keys.has(TK.WAN_V4) || keys.has(TK.WAN_LINK)) return "gateway";
  if (keys.has(TK.POE_CONTROL) && !keys.has(TK.WAN_LINK)) return "switch";
  if (keys.has(TK.STATUS)) return "ap";
  return "unknown";
}

function groupEntitiesByDevice(entities) {
  const map = new Map();
  for (const entity of entities) {
    if (!entity.device_id) continue;
    if (!map.has(entity.device_id)) map.set(entity.device_id, []);
    map.get(entity.device_id).push(entity);
  }
  return map;
}

function filterEntityIds(group, translationKeys) {
  return group.entities
    .filter((e) => translationKeys.includes(e.translation_key))
    .map((e) => e.entity_id);
}

// ---------------------------------------------------------------------------
// Custom card: Infrastructure device table
//
// Config shape:
//   deviceRows: [{
//     name, type, deviceId,
//     statusEntityId, cpuEntityId, memEntityId,
//     wanLinkEntityId,   // gateway only
//     poeEntityIds[],    // switch only
//   }]
//   allEntityIds: string[]   used for hass-change diffing
// ---------------------------------------------------------------------------

class OmadaDevicesTableCard extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._rendered = false;
    if (this._hass) this._renderAll();
  }

  set hass(hass) {
    const prev = this._hass;
    this._hass = hass;
    if (!this._rendered) {
      this._renderAll();
      return;
    }
    // Skip re-render if none of our entities changed
    const ids = this._config?.allEntityIds ?? [];
    if (prev && ids.every((id) => prev.states[id] === hass.states[id])) return;
    this._updateRows();
  }

  _renderAll() {
    if (!this._hass || !this._config) return;
    const rows = this._config.deviceRows ?? [];

    const th = (label, align = "left") =>
      `<th style="text-align:${align};padding:8px 8px;
                  border-bottom:1px solid var(--divider-color);
                  color:var(--secondary-text-color);font-size:0.78em;
                  text-transform:uppercase;letter-spacing:0.05em;
                  font-weight:500;white-space:nowrap;">${label}</th>`;

    this.innerHTML = `
      <ha-card>
        <div class="card-header"
             style="display:flex;justify-content:space-between;align-items:center;">
          <div class="name">Infrastructure</div>
          <div style="color:var(--secondary-text-color);font-size:0.8em;">
            ${rows.length} device${rows.length !== 1 ? "s" : ""}
          </div>
        </div>
        <div class="card-content" style="padding:0 16px 16px;overflow-x:auto;">
          <table style="width:100%;border-collapse:collapse;">
            <thead>
              <tr>
                ${th("")}
                ${th("Name")}
                ${th("Type")}
                ${th("Status")}
                ${th("CPU", "right")}
                ${th("Memory", "right")}
                ${th("Detail")}
              </tr>
            </thead>
            <tbody id="omada-devices-tbody"></tbody>
          </table>
        </div>
      </ha-card>`;

    this._rendered = true;
    this._updateRows();
    const tbody = this.querySelector("#omada-devices-tbody");
    if (tbody) {
      tbody.addEventListener("click", (e) => {
        const row = e.target.closest("tr[data-device-id]");
        if (row && row.dataset.deviceId) {
          window.history.pushState(
            null,
            "",
            `/config/devices/device/${row.dataset.deviceId}`,
          );
          window.dispatchEvent(new Event("location-changed"));
        }
      });
    }
  }

  _updateRows() {
    if (!this._hass || !this._rendered) return;
    const tbody = this.querySelector("#omada-devices-tbody");
    if (!tbody) return;
    const rows = this._config?.deviceRows ?? [];
    tbody.innerHTML = rows.map((d) => this._buildRow(d)).join("");
  }

  _buildRow(device) {
    const statusState = this._hass.states[device.statusEntityId];
    const cpuState = this._hass.states[device.cpuEntityId];
    const memState = this._hass.states[device.memEntityId];

    const statusVal = statusState?.state ?? "unknown";
    const isOk = statusVal === "connected";
    const isPending =
      statusVal === "pending" ||
      statusVal === "heartbeat_missed" ||
      statusVal === "isolated";

    const dotColor = isOk
      ? "var(--success-color,#4CAF50)"
      : isPending
        ? "var(--warning-color,#FF9800)"
        : "var(--error-color,#F44336)";

    const dot = `<span style="display:inline-block;width:8px;height:8px;
      border-radius:50%;background:${dotColor};margin-right:6px;
      flex-shrink:0;vertical-align:middle;"></span>`;

    const cpuNum = cpuState ? parseFloat(cpuState.state) : null;
    const memNum = memState ? parseFloat(memState.state) : null;
    const fmtPct = (v) => (v !== null && !isNaN(v) ? `${v.toFixed(0)}%` : "—");
    const pctColor = (v) => {
      if (v === null || isNaN(v)) return "var(--secondary-text-color)";
      if (v >= 85) return "var(--error-color,#F44336)";
      if (v >= 65) return "var(--warning-color,#FF9800)";
      return "inherit";
    };

    // Detail column
    let detail = "";
    if (device.type === "gateway" && device.wanLinkEntityId) {
      const wanState = this._hass.states[device.wanLinkEntityId];
      const wanOn = wanState?.state === "on";
      detail = `<span style="color:${wanOn ? "var(--success-color,#4CAF50)" : "var(--error-color,#F44336)"};">
        WAN ${wanOn ? "\u25CF" : "\u25CB"} ${wanOn ? "Connected" : "Down"}
      </span>`;
    } else if (device.type === "switch" && device.poeEntityIds?.length) {
      const poeOn = device.poeEntityIds.filter(
        (id) => this._hass.states[id]?.state === "on",
      ).length;
      detail = `<span style="color:var(--secondary-text-color);">
        PoE: ${poeOn}&thinsp;/&thinsp;${device.poeEntityIds.length} active
      </span>`;
    }

    const typeLabel =
      device.type === "gateway"
        ? "Gateway"
        : device.type === "switch"
          ? "Switch"
          : "Access Point";

    const icon =
      device.type === "gateway"
        ? "mdi:router-network"
        : device.type === "switch"
          ? "mdi:switch"
          : "mdi:wifi";

    const td = (content, extra = "") =>
      `<td style="padding:10px 8px;${extra}">${content}</td>`;
    const tds = (content, extra = "") =>
      `<td style="padding:10px 8px;color:var(--secondary-text-color);font-size:0.9em;${extra}">${content}</td>`;

    return `
      <tr style="border-bottom:1px solid var(--divider-color);cursor:pointer;" data-device-id="${escHtml(device.deviceId ?? "")}">
        ${td(`<ha-icon icon="${icon}" style="--mdi-icon-size:18px;
              color:var(--secondary-text-color);display:block;"></ha-icon>`)}
        ${td(`<span style="font-weight:500;">${escHtml(device.name)}</span>`)}
        ${tds(typeLabel)}
        ${td(dot, "width:24px;text-align:center;")}
        ${tds(fmtPct(cpuNum), `text-align:right;color:${pctColor(cpuNum)};`)}
        ${tds(fmtPct(memNum), `text-align:right;color:${pctColor(memNum)};`)}
        ${tds(detail || "\u2014")}
      </tr>`;
  }
}

customElements.define("omada-devices-table-card", OmadaDevicesTableCard);

// ---------------------------------------------------------------------------
// Custom card: Client panel
//
// Sections:
//   1. Search + filter bar
//   2. Live client table
//   3. Disabled clients (collapsible, starts open if any disabled)
//
// Config shape:
//   enabledEntityIds: string[]
//   disabledEntities: [{ entity_id, unique_id, name, config_entry_id }]
//   clientDevices: Record<entity_id, { device_id, device_name }>
// ---------------------------------------------------------------------------

class OmadaClientsPanelCard extends HTMLElement {
  constructor() {
    super();
    this._searchText = "";
    this._filter = "all"; // 'all' | 'online' | 'offline'
    this._pendingEnables = new Set();
    this._doneEnables = new Set();
    this._rendered = false;
    this._hass = null;
    this._config = null;
  }

  setConfig(config) {
    this._config = config;
    this._rendered = false;
    if (this._hass) this._renderAll();
  }

  set hass(hass) {
    const prev = this._hass;
    this._hass = hass;
    if (!this._rendered) {
      this._renderAll();
      return;
    }
    // Skip re-render if our tracker entities have not changed
    const ids = this._config?.enabledEntityIds ?? [];
    if (prev && ids.every((id) => prev.states[id] === hass.states[id])) return;
    this._updateTable();
  }

  // ── Full initial render ──────────────────────────────────────────────────

  _renderAll() {
    if (!this._hass || !this._config) return;
    const { enabledEntityIds = [], disabledEntities = [] } = this._config;
    const totalKnown = enabledEntityIds.length + disabledEntities.length;

    this.innerHTML = `
      <ha-card>
        <div class="card-header"
             style="display:flex;justify-content:space-between;align-items:center;">
          <div class="name">Clients</div>
          <div id="omada-client-badge"
               style="color:var(--secondary-text-color);font-size:0.8em;">
            ${totalKnown} known
          </div>
        </div>
        <div class="card-content" style="padding:0 16px 16px;">
          ${this._buildSearchBar()}
          <div style="overflow-x:auto;">
            <table style="width:100%;border-collapse:collapse;">
              <thead>
                <tr>
                  ${this._th("")}
                  ${this._th("Name")}
                  ${this._th("IP Address")}
                  ${this._th("Hostname")}
                  ${this._th("MAC")}
                  ${this._th("Last Seen", "right")}
                </tr>
              </thead>
              <tbody id="omada-clients-tbody"></tbody>
            </table>
          </div>
          ${this._buildDisabledSection(disabledEntities)}
        </div>
      </ha-card>`;

    this._rendered = true;
    this._attachListeners();
    this._updateTable();
  }

  _th(label, align = "left") {
    return `<th style="text-align:${align};padding:8px 8px;
                border-bottom:1px solid var(--divider-color);
                color:var(--secondary-text-color);font-size:0.78em;
                text-transform:uppercase;letter-spacing:0.05em;
                font-weight:500;white-space:nowrap;">${label}</th>`;
  }

  _buildDisabledSection(disabledEntities) {
    if (!disabledEntities.length) return "";
    const clientDevices = this._config.clientDevices ?? {};
    const rows = disabledEntities
      .map((e) => {
        const linked = clientDevices[e.entity_id];
        return `
        <div class="omada-dis-row"
             style="display:flex;align-items:center;justify-content:space-between;
                    padding:9px 0;border-bottom:1px solid var(--divider-color);">
          <div style="min-width:0;flex:1;">
            <div style="font-size:0.9em;font-weight:500;overflow:hidden;
                        text-overflow:ellipsis;white-space:nowrap;">
              ${escHtml(e.name)}
            </div>
            <div style="font-size:0.78em;color:var(--secondary-text-color);font-family:monospace;letter-spacing:0.03em;">
              ${escHtml(_macFromUniqueId(e.unique_id) ?? e.entity_id)}
            </div>
            ${
              linked
                ? `<span data-nav-device="${escHtml(linked.device_id)}"
                              style="display:inline-flex;align-items:center;gap:3px;
                                     margin-top:2px;font-size:0.78em;font-family:inherit;
                                     color:var(--primary-color);cursor:pointer;
                                     background:color-mix(in srgb,var(--primary-color) 10%,transparent);
                                     padding:1px 6px;border-radius:10px;">
                <ha-icon icon="mdi:devices" style="--mdi-icon-size:11px;display:inline-block;"></ha-icon>
                ${escHtml(linked.device_name)}
              </span>`
                : ""
            }
          </div>
          <button
            type="button"
            data-enable-entity="${escHtml(e.entity_id)}"
            data-enable-entry="${escHtml(e.config_entry_id ?? "")}"
            style="margin-left:12px;padding:5px 14px;background:transparent;
                   border:1px solid var(--primary-color);
                   color:var(--primary-color);border-radius:4px;
                   cursor:pointer;font-size:0.82em;white-space:nowrap;
                   flex-shrink:0;"
          >Enable</button>
        </div>`;
      })
      .join("");

    return `
      <div style="border:1px solid var(--warning-color,#FF9800);border-radius:8px;
                  margin-top:14px;overflow:hidden;">
        <div id="omada-dis-hdr"
             style="background:color-mix(in srgb,
                      var(--warning-color,#FF9800) 12%,transparent);
                    padding:10px 14px;display:flex;align-items:center;
                    justify-content:space-between;cursor:pointer;
                    user-select:none;">
          <div style="display:flex;align-items:center;gap:8px;">
            <ha-icon icon="mdi:account-off-outline"
                     style="--mdi-icon-size:18px;
                            color:var(--warning-color,#FF9800);"></ha-icon>
            <span style="font-weight:500;font-size:0.9em;">
              ${disabledEntities.length}&nbsp;client${disabledEntities.length !== 1 ? "s" : ""}
              disabled &mdash; enable to track presence
            </span>
          </div>
          <ha-icon id="omada-dis-chevron" icon="mdi:chevron-up"
                   style="--mdi-icon-size:18px;
                          color:var(--secondary-text-color);
                          transition:transform 0.2s;"></ha-icon>
        </div>
        <div id="omada-dis-body" style="padding:0 14px 6px;">
          ${rows}
        </div>
      </div>`;
  }

  _buildSearchBar() {
    const filterBtn = (val, label) =>
      `<button data-filter="${val}"
               style="padding:5px 14px;border-radius:20px;
                      border:1px solid var(--divider-color);
                      background:${this._filter === val ? "var(--primary-color)" : "transparent"};
                      color:${this._filter === val ? "var(--text-primary-color,#fff)" : "var(--primary-text-color)"};
                      cursor:pointer;font-size:0.82em;
                      transition:background 0.15s,color 0.15s;">
        ${label}
      </button>`;

    return `
      <div style="display:flex;align-items:center;gap:8px;
                  margin-bottom:12px;flex-wrap:wrap;">
        <div style="flex:1;min-width:160px;position:relative;">
          <ha-icon icon="mdi:magnify"
                   style="position:absolute;left:10px;top:50%;
                          transform:translateY(-50%);
                          --mdi-icon-size:16px;
                          color:var(--secondary-text-color);
                          pointer-events:none;"></ha-icon>
          <input id="omada-search" type="text"
                 placeholder="Search name, IP, hostname, MAC\u2026"
                 autocomplete="off"
                 style="width:100%;padding:7px 10px 7px 32px;
                        box-sizing:border-box;
                        border:1px solid var(--divider-color);
                        border-radius:20px;
                        background:var(--card-background-color,#fff);
                        color:var(--primary-text-color);
                        font-size:0.88em;outline:none;" />
        </div>
        <div id="omada-filter-btns" style="display:flex;gap:6px;flex-shrink:0;">
          ${filterBtn("all", "All")}
          ${filterBtn("online", "Online")}
          ${filterBtn("offline", "Offline")}
        </div>
      </div>`;
  }

  // ── Event listeners (attached once after full render) ────────────────────

  _attachListeners() {
    // Search
    const input = this.querySelector("#omada-search");
    if (input) {
      input.addEventListener("input", (e) => {
        this._searchText = e.target.value;
        this._updateTable();
      });
    }

    // Filter buttons
    this.querySelectorAll("[data-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._filter = btn.dataset.filter;
        this.querySelectorAll("[data-filter]").forEach((b) => {
          const active = b.dataset.filter === this._filter;
          b.style.background = active ? "var(--primary-color)" : "transparent";
          b.style.color = active
            ? "var(--text-primary-color,#fff)"
            : "var(--primary-text-color)";
        });
        this._updateTable();
      });
    });

    // Disabled section toggle
    const hdr = this.querySelector("#omada-dis-hdr");
    const body = this.querySelector("#omada-dis-body");
    const chevron = this.querySelector("#omada-dis-chevron");
    if (hdr && body) {
      let open = false; // starts collapsed
      body.style.display = "none";
      if (chevron) chevron.style.transform = "rotate(180deg)";
      hdr.addEventListener("click", () => {
        open = !open;
        body.style.display = open ? "" : "none";
        if (chevron) chevron.style.transform = open ? "" : "rotate(180deg)";
      });
    }

    // Enable buttons
    this.querySelectorAll("[data-enable-entity]").forEach((btn) =>
      btn.addEventListener("click", () => this._handleEnable(btn)),
    );

    // Device badge → navigate to HA device page (anywhere in the card)
    this.addEventListener("click", (e) => {
      const badge = e.target.closest("[data-nav-device]");
      if (badge) {
        e.stopPropagation();
        window.history.pushState(
          null,
          "",
          `/config/devices/device/${badge.dataset.navDevice}`,
        );
        window.dispatchEvent(new Event("location-changed"));
      }
    });

    // Client row click → more-info dialog
    const clientsTbody = this.querySelector("#omada-clients-tbody");
    if (clientsTbody) {
      clientsTbody.addEventListener("click", (e) => {
        if (e.target.closest("[data-nav-device]")) return;
        const row = e.target.closest("tr[data-entity-id]");
        if (row) {
          this.dispatchEvent(
            new CustomEvent("hass-more-info", {
              detail: { entityId: row.dataset.entityId },
              bubbles: true,
              composed: true,
            }),
          );
        }
      });
    }
  }

  async _handleEnable(btn) {
    if (!this._hass) return;
    const entityId = btn.dataset.enableEntity;
    const configEntryId = btn.dataset.enableEntry;

    this._pendingEnables.add(entityId);
    btn.disabled = true;
    btn.textContent = "Enabling\u2026";
    btn.style.borderColor = "var(--disabled-color,#9E9E9E)";
    btn.style.color = "var(--disabled-color,#9E9E9E)";

    try {
      await this._hass.callWS({
        type: "config/entity_registry/update",
        entity_id: entityId,
        disabled_by: null,
      });
      if (configEntryId) {
        await this._hass.callWS({
          type: "config_entries/reload",
          entry_id: configEntryId,
        });
      }
      this._pendingEnables.delete(entityId);
      this._doneEnables.add(entityId);
      btn.textContent = "Enabled \u2713";
      btn.style.borderColor = "var(--success-color,#4CAF50)";
      btn.style.color = "var(--success-color,#4CAF50)";
    } catch (_err) {
      this._pendingEnables.delete(entityId);
      btn.textContent = "Error \u2014 retry";
      btn.style.borderColor = "var(--error-color,#F44336)";
      btn.style.color = "var(--error-color,#F44336)";
      btn.disabled = false;
    }
  }

  // ── Live table update (runs on every relevant hass change) ───────────────

  _updateTable() {
    if (!this._hass || !this._rendered) return;
    const tbody = this.querySelector("#omada-clients-tbody");
    if (!tbody) return;

    const { enabledEntityIds = [], disabledEntities = [] } = this._config;
    const search = this._searchText.trim().toLowerCase();

    let rows = enabledEntityIds
      .map((id) => {
        const s = this._hass.states[id];
        if (!s) return null;
        const linked = (this._config.clientDevices ?? {})[id];
        return {
          entity_id: id,
          name: s.attributes.friendly_name ?? id,
          ip: s.attributes.ip ?? "\u2014",
          hostname: s.attributes.host_name ?? "\u2014",
          mac: s.attributes.mac ?? "\u2014",
          isHome: s.state === "home",
          lastSeen: s.last_changed
            ? new Date(s.last_changed).toLocaleString()
            : "\u2014",
          linked_device_id: linked?.device_id ?? null,
          linked_device_name: linked?.device_name ?? null,
        };
      })
      .filter(Boolean);

    // Filter by status
    if (this._filter === "online") rows = rows.filter((r) => r.isHome);
    else if (this._filter === "offline") rows = rows.filter((r) => !r.isHome);

    // Filter by search text
    if (search) {
      rows = rows.filter(
        (r) =>
          r.name.toLowerCase().includes(search) ||
          r.ip.toLowerCase().includes(search) ||
          r.hostname.toLowerCase().includes(search) ||
          r.mac.toLowerCase().includes(search),
      );
    }

    // Sort: online first, then alphabetical
    rows.sort((a, b) => b.isHome - a.isHome || a.name.localeCompare(b.name));

    // Update the count badge
    const badge = this.querySelector("#omada-client-badge");
    if (badge) {
      const onlineCount = enabledEntityIds.filter(
        (id) => this._hass.states[id]?.state === "home",
      ).length;
      const total = enabledEntityIds.length + disabledEntities.length;
      badge.textContent = `${onlineCount}\u202f/\u202f${total} online`;
    }

    if (!rows.length) {
      const msg = search
        ? "No clients match your search"
        : this._filter !== "all"
          ? `No ${this._filter} clients`
          : "No clients available";
      tbody.innerHTML = `
        <tr>
          <td colspan="6"
              style="padding:20px;text-align:center;
                     color:var(--secondary-text-color);">${msg}</td>
        </tr>`;
      return;
    }

    const tds = (content, extra = "") =>
      `<td style="padding:9px 8px;color:var(--secondary-text-color);
                  font-size:0.88em;${extra}">${content}</td>`;

    tbody.innerHTML = rows
      .map(
        (r) => `
        <tr style="border-bottom:1px solid var(--divider-color);cursor:pointer;" data-entity-id="${escHtml(r.entity_id)}">
          <td style="padding:9px 8px;width:16px;">
            <span style="display:inline-block;width:8px;height:8px;
                         border-radius:50%;vertical-align:middle;
                         background:${
                           r.isHome
                             ? "var(--success-color,#4CAF50)"
                             : "var(--disabled-color,#9E9E9E)"
                         };"></span>
          </td>
          <td style="padding:9px 8px;font-weight:${r.isHome ? "500" : "400"};">
            ${escHtml(r.name)}
            ${
              r.linked_device_id
                ? `<div style="margin-top:2px;">
              <span data-nav-device="${escHtml(r.linked_device_id)}"
                    style="display:inline-flex;align-items:center;gap:3px;
                           font-size:0.75em;font-weight:400;
                           color:var(--primary-color);cursor:pointer;
                           background:color-mix(in srgb,var(--primary-color) 10%,transparent);
                           padding:1px 6px;border-radius:10px;line-height:1.6;">
                <ha-icon icon="mdi:devices" style="--mdi-icon-size:11px;display:inline-block;"></ha-icon>
                ${escHtml(r.linked_device_name ?? "")}
              </span>
            </div>`
                : ""
            }
          </td>
          ${tds(escHtml(r.ip))}
          ${tds(escHtml(r.hostname))}
          ${tds(escHtml(r.mac))}
          ${tds(escHtml(r.lastSeen), "text-align:right;")}
        </tr>`,
      )
      .join("");
  }
}

customElements.define("omada-clients-panel-card", OmadaClientsPanelCard);

// ---------------------------------------------------------------------------
// Build cards for the single-page view
// ---------------------------------------------------------------------------

function buildSinglePageCards(options, hass) {
  const {
    gateways,
    switches,
    aps,
    enabledClients,
    disabledClients,
    clients,
    updateEntities,
    clientDevices = {},
  } = options;

  const allDeviceGroups = [...gateways, ...switches, ...aps];
  const deviceRows = [];
  const allDeviceEntityIds = [];

  for (const gw of gateways) {
    const statusId = gw.entities.find(
      (e) => e.translation_key === TK.STATUS,
    )?.entity_id;
    const cpuId = filterEntityIds(gw, [TK.CPU])[0];
    const memId = filterEntityIds(gw, [TK.MEM])[0];
    const wanLinkId = filterEntityIds(gw, [TK.WAN_LINK])[0];
    const ids = [statusId, cpuId, memId, wanLinkId].filter(Boolean);
    allDeviceEntityIds.push(...ids);
    deviceRows.push({
      name: gw.deviceName,
      type: "gateway",
      deviceId: gw.deviceId,
      statusEntityId: statusId,
      cpuEntityId: cpuId,
      memEntityId: memId,
      wanLinkEntityId: wanLinkId,
      poeEntityIds: [],
    });
  }

  for (const sw of switches) {
    const statusId = sw.entities.find(
      (e) => e.translation_key === TK.STATUS,
    )?.entity_id;
    const cpuId = filterEntityIds(sw, [TK.CPU])[0];
    const memId = filterEntityIds(sw, [TK.MEM])[0];
    const poeIds = filterEntityIds(sw, [TK.POE_CONTROL]);
    const ids = [statusId, cpuId, memId, ...poeIds].filter(Boolean);
    allDeviceEntityIds.push(...ids);
    deviceRows.push({
      name: sw.deviceName,
      type: "switch",
      deviceId: sw.deviceId,
      statusEntityId: statusId,
      cpuEntityId: cpuId,
      memEntityId: memId,
      wanLinkEntityId: undefined,
      poeEntityIds: poeIds,
    });
  }

  for (const ap of aps) {
    const statusId = ap.entities.find(
      (e) => e.translation_key === TK.STATUS,
    )?.entity_id;
    const cpuId = filterEntityIds(ap, [TK.CPU])[0];
    const memId = filterEntityIds(ap, [TK.MEM])[0];
    const ids = [statusId, cpuId, memId].filter(Boolean);
    allDeviceEntityIds.push(...ids);
    deviceRows.push({
      name: ap.deviceName,
      type: "ap",
      deviceId: ap.deviceId,
      statusEntityId: statusId,
      cpuEntityId: cpuId,
      memEntityId: memId,
      wanLinkEntityId: undefined,
      poeEntityIds: [],
    });
  }

  const totalDevices = allDeviceGroups.length;
  const totalClients = clients.length;

  const cards = [];

  // Header
  cards.push({
    type: "markdown",
    content:
      `## ${escHtml(hass.config.location_name)} Network\n` +
      `*Powered by TP-Link Omada*` +
      `\u00a0|\u00a0 **${totalDevices}** device${totalDevices !== 1 ? "s" : ""}` +
      `\u00a0|\u00a0 **${totalClients}** known client${totalClients !== 1 ? "s" : ""}`,
  });

  // Device table
  if (deviceRows.length) {
    cards.push({
      type: "custom:omada-devices-table-card",
      deviceRows,
      allEntityIds: allDeviceEntityIds,
    });
  }

  // Client panel (search + filter + enable + table)
  cards.push({
    type: "custom:omada-clients-panel-card",
    enabledEntityIds: enabledClients.map((e) => e.entity_id),
    disabledEntities: disabledClients.map((e) => ({
      entity_id: e.entity_id,
      unique_id: e.unique_id,
      name: e.name || e.original_name || e.entity_id,
      config_entry_id: e.config_entry_id,
    })),
    clientDevices,
  });

  // Conditional firmware alert
  if (updateEntities.length) {
    cards.push({
      type: "entity-filter",
      entities: updateEntities.map((e) => e.entity_id),
      state_filter: [{ operator: "!=", value: "off" }],
      card: {
        type: "entities",
        title: "Firmware Updates Available",
        icon: "mdi:update",
        show_header_toggle: false,
      },
      show_empty: false,
    });
  }

  return cards;
}

// ---------------------------------------------------------------------------
// Dashboard strategy — single view
// ---------------------------------------------------------------------------

class OmadaNetworkDashboardStrategy extends HTMLElement {
  static getCreateSuggestions(_hass) {
    return {
      title: "Omada Network",
      icon: "mdi:router-network",
    };
  }

  static async generate(config, hass) {
    const [allEntities, allDevices] = await Promise.all([
      hass.callWS({ type: "config/entity_registry/list" }),
      hass.callWS({ type: "config/device_registry/list" }),
    ]);

    const entryFilter = (e) =>
      !config.config_entry_id || e.config_entry_id === config.config_entry_id;

    // Enabled non-tracker omada entities for device grouping
    const omadaEnabled = allEntities.filter(
      (e) =>
        e.platform === "tplink_omada" &&
        e.disabled_by === null &&
        !e.entity_id.startsWith("device_tracker.") &&
        entryFilter(e),
    );

    // All device_tracker entities regardless of disabled state
    const allTrackers = allEntities.filter(
      (e) =>
        e.platform === "tplink_omada" &&
        e.entity_id.startsWith("device_tracker.") &&
        entryFilter(e),
    );

    const omadaDeviceMap = new Map(
      allDevices
        .filter((d) =>
          d.identifiers.some(([domain]) => domain === "tplink_omada"),
        )
        .map((d) => [d.id, d]),
    );

    const entitiesByDevice = groupEntitiesByDevice(omadaEnabled);
    const gateways = [];
    const switches = [];
    const aps = [];

    for (const [deviceId, entities] of entitiesByDevice) {
      const device = omadaDeviceMap.get(deviceId);
      const deviceName = device
        ? device.name_by_user || device.name || deviceId
        : deviceId;
      const group = { deviceId, deviceName, entities };
      const type = classifyDevice(entities);
      if (type === "gateway") gateways.push(group);
      else if (type === "switch") switches.push(group);
      else if (type === "ap") aps.push(group);
    }

    const updateEntities = omadaEnabled.filter((e) =>
      e.entity_id.startsWith("update."),
    );
    const enabledClients = allTrackers.filter((e) => e.disabled_by === null);
    const disabledClients = allTrackers.filter((e) => e.disabled_by !== null);

    const allDevicesMap = new Map(allDevices.map((d) => [d.id, d]));
    const clientDevices = {};
    for (const tracker of allTrackers) {
      if (tracker.device_id && !omadaDeviceMap.has(tracker.device_id)) {
        const dev = allDevicesMap.get(tracker.device_id);
        if (dev) {
          clientDevices[tracker.entity_id] = {
            device_id: tracker.device_id,
            device_name: dev.name_by_user || dev.name || tracker.device_id,
          };
        }
      }
    }

    const options = {
      gateways,
      switches,
      aps,
      clients: allTrackers,
      enabledClients,
      disabledClients,
      updateEntities,
      clientDevices,
    };

    return {
      title: config.title ?? "Omada Network",
      views: [
        {
          title: "Network",
          path: "network",
          icon: "mdi:view-dashboard",
          cards: buildSinglePageCards(options, hass),
        },
      ],
    };
  }
}

// ---------------------------------------------------------------------------
// Register custom elements
// ---------------------------------------------------------------------------

customElements.define(
  "ll-strategy-dashboard-omada-network",
  OmadaNetworkDashboardStrategy,
);

// ---------------------------------------------------------------------------
// Register with Community Dashboards picker (HA 2026.5+)
// ---------------------------------------------------------------------------

window.customStrategies = window.customStrategies || [];
window.customStrategies.push({
  type: "omada-network",
  strategyType: "dashboard",
  name: "Omada Network",
  description:
    "Live view of all TP-Link Omada devices, clients, and port controls.",
  documentationURL: "https://www.home-assistant.io/integrations/tplink_omada",
});
