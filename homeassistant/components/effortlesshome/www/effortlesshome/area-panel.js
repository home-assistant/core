import { html, css, LitElement } from "https://cdn.jsdelivr.net/gh/lit/dist@2/core/lit-core.min.js";
import "https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js";

class AreaPanel extends LitElement {
  static properties = {
    hass: {},
    areas: { type: Array },
    areaEntityMap: { type: Object },
    domains: { type: Array },
    selectedDomain: { type: String },
  };

  static styles = css`
    :host {
      display: block;
      background-color: var(--lovelace-background, var(--primary-background-color));
      color: var(--primary-text-color);
      font-family: var(--paper-font-body1_-_font-family, "Arial", sans-serif);
      transition: background-color 0.3s, color 0.3s;
      min-height: 100vh;
    }

    .top-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 20px;
      background: var(--card-background-color);
      border-bottom: 1px solid var(--divider-color);
      box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0, 0, 0, 0.1));
      border-radius: var(--ha-card-border-radius, 12px);
      margin: 1rem;
    }

    .back-arrow {
      font-size: 24px;
      color: var(--primary-color);
      cursor: pointer;
      user-select: none;
      transition: color 0.3s;
    }

    .back-arrow:hover {
      color: var(--accent-color);
    }

    .domain-select {
      padding: 6px 10px;
      font-size: 14px;
      border-radius: 6px;
      border: 1px solid var(--divider-color);
      background-color: var(--secondary-background-color);
      color: var(--primary-text-color);
      transition: border-color 0.3s, background-color 0.3s;
    }

    .domain-select:focus {
      outline: none;
      border-color: var(--primary-color);
    }

    .container {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 20px;
      padding: 20px;
    }

    .area-box {
      background-color: var(--card-background-color);
      border-radius: var(--ha-card-border-radius, 12px);
      padding: 16px;
      display: flex;
      flex-direction: column;
      box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0, 0, 0, 0.15));
      transition: background-color 0.3s, box-shadow 0.3s;
    }

    .area-box h3 {
      text-align: center;
      margin: 0 0 12px;
      font-size: 1.1rem;
      font-weight: 600;
      color: var(--primary-text-color);
    }

    .tile-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;
      min-height: 50px;
    }

    .entity-tile {
      background-color: var(--secondary-background-color);
      color: var(--primary-text-color);
      padding: 10px;
      border-radius: 8px;
      box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0, 0, 0, 0.1));
      cursor: grab;
      text-align: center;
      transition: transform 0.2s, background-color 0.3s;
    }

    .instructions {
      background: var(--card-background-color);
      border: 1px solid var(--divider-color);
      border-left: 4px solid var(--primary-color);
      border-radius: 8px;
      padding: 12px 16px;
      margin: 1rem;
      display: flex;
      align-items: center;
      gap: 12px;
      color: var(--secondary-text-color);
      font-size: 0.95rem;
      box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0, 0, 0, 0.1));
    }
    
    .instructions ha-icon {
      color: var(--primary-color);
      flex-shrink: 0;
    }

    .instructions strong {
      color: var(--primary-text-color);
    }

    .entity-tile:hover {
      background-color: var(--accent-color);
      color: var(--text-primary-color, #fff);
      transform: translateY(-2px);
    }

    .entity-tile:active {
      cursor: grabbing;
      transform: scale(0.98);
    }
  `;

  constructor() {
    super();
    this.areas = [];
    this.areaEntityMap = {};
    this.domains = [];
    this.selectedDomain = "";
  }

  firstUpdated() {
    this._buildAreaTiles();
  }

  updated(changedProps) {
    if (changedProps.has("hass")) {
      this._buildAreaTiles();
    }
  }

  async _buildAreaTiles() {
    if (!this.hass || !this.hass.areas || !this.hass.states || !this.hass.entities) return;

    const excludedDomains = [
      "person",
      "backup",
      "automation",
      "script",
      "device_tracker",
      "calendar",
      "area",
      "zone",
      "label",
      "sun",
      "tts",
      "text",
      "ai_task",
      "group",
      "conversation",
      "event",
      "weather",
      "effortlesshome",
    ];

    const rawAreas = Object.values(this.hass.areas);
    const areas = [...rawAreas, { name: "Unknown", area_id: "unknown" }];
    const entities = Object.values(this.hass.states);
    const areaEntityMap = {};
    const domainsSet = new Set();

    for (const area of areas) {
      areaEntityMap[area.area_id] = [];
    }

    for (const ent of entities) {
      const domain = ent.entity_id.split(".")[0];
      if (excludedDomains.includes(domain)) continue;

      domainsSet.add(domain);

      const areaId = this.hass.entities[ent.entity_id]?.area_id;
      const assignedArea = areaId || "unknown";
      if (!areaEntityMap[assignedArea]) {
        areaEntityMap[assignedArea] = [];
      }
      areaEntityMap[assignedArea].push(ent.entity_id);
    }

    this.areas = areas;
    this.areaEntityMap = areaEntityMap;
    this.domains = Array.from(domainsSet).sort();

    if (!this.selectedDomain && this.domains.length > 0) {
      this.selectedDomain = this.domains[0];
    }

    await this.updateComplete;
    this._initSortable();
  }

  _initSortable() {
    this.areas.forEach((area) => {
      const container = this.renderRoot.querySelector(`#grid-${area.area_id}`);
      if (!container) return;
      Sortable.create(container, {
        group: "shared",
        animation: 150,
        onAdd: (evt) => {
          const entityId = evt.item.dataset.entity;
          const newAreaId = area.area_id === "unknown" ? null : area.area_id;

          this.hass.callService("effortlesshome", "update_entity", {
            entity_id: entityId,
            area_id: newAreaId,
          });
        },
      });
    });
  }

  _getFriendlyName(entityId) {
    return this.hass.states[entityId]?.attributes.friendly_name || entityId;
  }

  _handleDomainChange(e) {
    this.selectedDomain = e.target.value;
  }

  render() {
    return html`
      <div class="top-bar">
        <div class="back-arrow" @click=${() => history.back()}>&larr;</div>
        <select class="domain-select" @change=${this._handleDomainChange}>
          ${this.domains.map(
      (domain) => html`
              <option ?selected=${domain === this.selectedDomain}>
                ${domain}
              </option>
            `
    )}
        </select>
      </div>

      <div class="instructions">
        <ha-icon icon="mdi:information-outline"></ha-icon>
        <div>
          <strong>Instructions:</strong> Drag and drop entities between the boxes to assign them to different areas. The changes are saved automatically.
        </div>
      </div>

      <div class="container">
        ${this.areas.map(
      (area) => html`
            <div class="area-box">
              <h3>${area.name}</h3>
              <div class="tile-grid" id="grid-${area.area_id}">
                ${this.areaEntityMap[area.area_id]
          ?.filter(
            (eid) => eid.split(".")[0] === this.selectedDomain
          )
          .map(
            (eid) => html`
                      <div class="entity-tile" data-entity="${eid}">
                        ${this._getFriendlyName(eid)}
                      </div>
                    `
          )}
              </div>
            </div>
          `
    )}
      </div>
    `;
  }
}

customElements.define("effortlesshome-area-panel", AreaPanel);
