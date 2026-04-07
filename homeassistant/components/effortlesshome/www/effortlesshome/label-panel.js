import { html, css, LitElement } from "https://cdn.jsdelivr.net/gh/lit/dist@2/core/lit-core.min.js";
import "https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js";

class LabelPanel extends LitElement {
  static properties = {
    hass: {},
    labels: { type: Array },
    labelEntityMap: { type: Object },
    selectedDomain: { type: String },
    allDomains: { type: Array },
  };

  static styles = css`
    :host {
      display: block;
      color: var(--primary-text-color);
      background-color: var(--lovelace-background, var(--primary-background-color));
      font-family: var(--primary-font-family, Roboto, sans-serif);
    }

    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 20px;
      background: var(--card-background-color);
      border-bottom: 1px solid var(--divider-color);
      color: var(--primary-text-color);
      box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,0.1));
    }

    .back-arrow {
      cursor: pointer;
      font-size: 20px;
      margin-right: 12px;
      color: var(--primary-color);
      transition: color 0.3s;
    }

    .back-arrow:hover {
      color: var(--accent-color);
    }

    select {
      padding: 6px 10px;
      border-radius: 6px;
      border: 1px solid var(--divider-color);
      background: var(--card-background-color);
      color: var(--primary-text-color);
      font-size: 14px;
      transition: border 0.3s;
    }

    select:focus {
      outline: none;
      border-color: var(--primary-color);
    }

    .container {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 20px;
      padding: 20px;
      box-sizing: border-box;
    }

    .label-box {
      background: var(--ha-card-background, var(--card-background-color));
      border-radius: 12px;
      padding: 16px;
      box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0, 0, 0, 0.1));
      display: flex;
      flex-direction: column;
      transition: background 0.3s, box-shadow 0.3s;
    }

    .label-box h3 {
      text-align: center;
      margin-bottom: 12px;
      color: var(--primary-text-color);
      font-weight: 600;
    }

    .tile-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;
      min-height: 50px;
    }

    .entity-tile {
      background: var(--card-background-color);
      color: var(--primary-text-color);
      padding: 10px;
      border-radius: 8px;
      border: 1px solid var(--divider-color);
      box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0, 0, 0, 0.1));
      cursor: grab;
      text-align: center;
      transition: background 0.3s, transform 0.1s;
    }

    .instructions {
      background: var(--card-background-color);
      border: 1px solid var(--divider-color);
      border-left: 4px solid var(--primary-color);
      border-radius: 8px;
      padding: 12px 16px;
      margin: 1rem 1.25rem;
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
      background: var(--ha-card-background-hover, var(--secondary-background-color));
      transform: scale(1.02);
    }
  `;

  constructor() {
    super();
    this.labels = [];
    this.labelEntityMap = {};
    this.selectedDomain = "";
    this.allDomains = [];
  }

  firstUpdated() {
    this._buildLabelTiles();
  }

  updated(changedProps) {
    if (changedProps.has("hass")) {
      this._buildLabelTiles();
    }
  }

  async _buildLabelTiles() {
    if (!this.hass || !this.hass.states || !this.hass.entities) return;

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

    const rawLabels = await this.hass.callWS({ type: "config/label_registry/list" });
    const labels = [...rawLabels, { name: "No Labels", label_id: "no_labels" }];
    const entities = Object.values(this.hass.states);

    const labelEntityMap = {};
    const domainSet = new Set();

    for (const label of labels) {
      labelEntityMap[label.label_id] = [];
    }

    for (const ent of entities) {
      const domain = ent.entity_id.split(".")[0];
      if (excludedDomains.includes(domain) || !this.hass.entities[ent.entity_id]) continue;

      domainSet.add(domain);

      const entityLabels = this.hass.entities[ent.entity_id].labels || [];
      const validLabels = entityLabels.filter((labelId) => labelEntityMap[labelId]);

      if (validLabels.length === 0) {
        labelEntityMap["no_labels"].push(ent.entity_id);
      } else {
        validLabels.forEach((labelId) => {
          if (!labelEntityMap[labelId].includes(ent.entity_id)) {
            labelEntityMap[labelId].push(ent.entity_id);
          }
        });
      }
    }

    this.labels = labels;
    this.labelEntityMap = labelEntityMap;
    this.allDomains = Array.from(domainSet).sort();
    if (!this.selectedDomain && this.allDomains.length > 0) {
      this.selectedDomain = this.allDomains[0];
    }

    await this.updateComplete;
    this._initSortable();
  }

  _initSortable() {
    this.labels.forEach((label) => {
      const container = this.renderRoot.querySelector(`#grid-${label.label_id}`);
      if (!container) return;

      Sortable.create(container, {
        group: {
          name: "shared",
          pull: "clone",
          put: label.label_id !== "no_labels",
        },
        animation: 150,
        onAdd: (evt) => {
          const entityId = evt.item.dataset.entity;
          const newLabelId = label.label_id;

          this.hass.callService("effortlesshome", "add_label_to_entity", {
            entity_id: entityId,
            label: newLabelId,
          });
        },
      });
    });
  }

  _getFriendlyName(entityId) {
    return this.hass.states[entityId]?.attributes.friendly_name || entityId;
  }

  _onDomainChange(e) {
    this.selectedDomain = e.target.value;
  }

  render() {
    return html`
      <div class="header">
        <span class="back-arrow" @click=${() => history.back()}>←</span>
        <select @change=${this._onDomainChange}>
          ${this.allDomains.map(
      (domain) =>
        html`<option ?selected=${domain === this.selectedDomain}>${domain}</option>`
    )}
        </select>
      </div>

      <div class="instructions">
        <ha-icon icon="mdi:information-outline"></ha-icon>
        <div>
          <strong>Instructions:</strong> Drag and drop entities into the labels to assign them. Entities can have multiple labels.
        </div>
      </div>

      <div class="container">
        ${this.labels.map(
      (label) => html`
            <div class="label-box">
              <h3>${label.name}</h3>
              <div class="tile-grid" id="grid-${label.label_id}">
                ${this.labelEntityMap[label.label_id]
          ?.filter((eid) => eid.startsWith(this.selectedDomain + "."))
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

customElements.define("effortlesshome-label-panel", LabelPanel);
