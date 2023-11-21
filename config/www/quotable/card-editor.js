class QuotableCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tags = [];
    this._authors = [];
  }

  set hass(hass) {
    this._hass = hass;
  }

  setConfig(config) {
    this._config = config;
    console.log(this._config);
  }

  async connectedCallback() {
    this.loadOptions();
  }

  async loadOptions() {
    try {
      console.log("in load options");

      if (!this._config.entity) {
        console.error("Entity not defined in configuration.");
        return;
      }

      const serviceData = {
        entity_id: this._config.entity,
      };

      const tags = {
        domain: "quotable",
        service: "fetch_all_tags",
        type: "call_service",
        return_response: true,
        service_data: serviceData,
      };

      const authors = {
        domain: "quotable",
        service: "search_authors",
        type: "call_service",
        return_response: true,
        service_data: serviceData,
      };

      // Call quotable service to fetch all tags
      const response_tags = await this._hass.callWS(tags);

      const response_authors = await this._hass.callWs(authors);

      if (response_tags && response_tags.response) {
        // Update the _tags property with the fetched tags
        this._tags = Object.values(response_tags.response);
        console.log(this._tags);
      }

      if (response_authors && response_authors.response) {
        this._authors = Object.values(response_authors.response);
        console.log(this._authors);
      }
    } catch (error) {
      console.error("Error fetching options:", error);
    }
    this.renderForm();
  }

  async searchAuthors() {
    try {
      console.log("in load options");

      if (!this._config.entity) {
        console.error("Entity not defined in configuration.");
        return;
      }

      const serviceData = {
        entity_id: this._config.entity,
      };

      const authors = {
        domain: "quotable",
        service: "search_authors",
        type: "call_service",
        return_response: true,
        service_data: serviceData,
      };

      const response_authors = await this._hass.callWs(authors);

      if (response_authors && response_authors.response) {
        this._authors = Object.values(response_authors.response);
        console.log(this._authors);
      }
    } catch (error) {
      console.error("Error fetching options:", error);
    }
    this.renderForm();
  }

  renderForm() {
    this.shadowRoot.innerHTML = `
    <div>
    <label for="browser">Authors:</label>
    <input type="search" id="myInput" onsearch="myFunction()">
    </div>
    `;
  }
}

customElements.define("quotable-card-editor", QuotableCardEditor);
