class QuotableCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tags = [];
    this._authors = [];
    this._selectedTags = [];
    this._selectedAuthors = [];
    this.intervalValue = 300;
    this._selectedAuthorSlug = [];
  }

  set hass(hass) {
    this._hass = hass;
  }

  setConfig(config) {
    this._config = config;
    this.configChanged(config);
  }

  async connectedCallback() {
    this.loadOptions();
    this.addEventListener("config-changed", this.handleConfigChanged);
  }
  handleConfigChanged(event) {
    console.log("Configuration changed:", event.detail.config);
  }
  async loadOptions() {
    try {
      console.log("in load options");
      if (!this._config.entity) {
        console.error("Entity not defined in configuration.");
        return;
      }

      //Data payload that is transmitted as part of the service call
      const serviceData = {
        entity_id: this._config.entity,
      };

      const authorMessage = {
        domain: "quotable",
        service: "fetch_all_authors",
        type: "call_service",
        return_response: true,
        service_data: serviceData,
      };

      //Message object used when calling quotable service
      const tagMessage = {
        domain: "quotable",
        service: "fetch_all_tags",
        type: "call_service",
        return_response: true,
        service_data: serviceData,
      };

      // Call quotable service to fetch all authors
      const responseAuthor = await this._hass.callWS(authorMessage);
      // Call quotable service to fetch all tags
      const responseTags = await this._hass.callWS(tagMessage);

      if (responseAuthor && responseAuthor.response) {
        // Update the authors property with the fetched authors
        this._authors = Object.values(responseAuthor.response);
      }

      if (responseTags && responseTags.response) {
        // Update the _tags property with the fetched tags
        this._tags = Object.values(responseTags.response);
      }
    } catch (error) {
      console.error("Error fetching options:", error);
    }
    this.renderForm();
  }

  //Render the visual representation
  renderForm() {
    // Add the container to the shadow DOM
    this.shadowRoot.innerHTML = `

    <style>
      div {
        margin: 20px;
      }

      select[multiple] {
        width: 100%;
        height: 100px;
        border: 1px solid #ccc;
        border-radius: 5px;
        background-color: #fff;
        padding: 5px;
        overflow-y: auto;
      }
      option {
        padding: 5px;
        cursor: pointer;
      }



      input[type="text"] {
        width: 100%;
        padding: 5px;
        margin-bottom: 10px;
      }

            input[type="range"] {
        width: 80%;
        height: 10px;
        border: 1px solid #ccc;
        border-radius: 5px;
        background-color: #fdd835;
        outline: none;
      }


            input[type="range"]::-webkit-slider-thumb {
        -webkit-appearance: none;
        width: 20px;
        height: 20px;
        background-color: #007BFF;
        border: 1px solid #007BFF;
        border-radius: 50%;
        cursor: pointer;
      }

      input[type="text"] {
        width: 100%;
        padding: 5px;
        margin-bottom: 10px;
      }
    </style>

      <form id="form">
    <div>
    <label for="authorSelect">Select Authors:</label>
    <span id="selectedAuthorLabel"></span>
    <input type="text" id="authorInput" placeholder="Search here">
    <select id="authorSelect" multiple>
      ${this._authors
        .map((author) => `<option value="${author}">${author}</option>`)
        .join("")}
    </select>
  </div>

  <div>
    <label for="tagSelect">Select Categories:</label>
    <input type="text" id="selectedTags" readonly  placeholder="Select from list">
    <select id="tagSelect" multiple>
      ${this._tags
        .map((tag) => `<option value="${tag}">${tag}</option>`)
        .join("")}
    </select>
  </div>

  <div>
    <label for="slider">Select Update Interval(mins):</label>
    <input type="range" id="slider" min="1" max="60" value="50">
    <span id="updateIntervalLabel">50</span>
  </div>
  </form>
  `;

    // Add references to the input and multiselect elements
    const authorInput = this.shadowRoot.getElementById("authorInput");
    const authorSelect = this.shadowRoot.getElementById("authorSelect");
    const selectedTags = this.shadowRoot.getElementById("selectedTags");
    const tagSelect = this.shadowRoot.getElementById("tagSelect");
    const updateIntervalSlider = this.shadowRoot.getElementById("slider");
    const updateIntervalLabel = this.shadowRoot.getElementById(
      "updateIntervalLabel"
    );
    const selectedAuthorLabel = this.shadowRoot.getElementById(
      "selectedAuthorLabel"
    );
    const form = this.shadowRoot.getElementById("form");

    // Add  event listener to search author
    authorInput.addEventListener("keyup", () => {
      this.searchAuthor(authorInput.value);
    });

    // Add click event listener to update selected author list
    authorSelect.addEventListener("click", (event) => {
      const selectedOption = event.target;

      if (selectedOption.tagName === "OPTION") {
        // Toggle the background color of the selected option
        selectedOption.style.backgroundColor =
          selectedOption.style.backgroundColor === "#007BFF"
            ? "#fff"
            : "#007BFF";

        // Toggle the text color of the selected option
        selectedOption.style.color =
          selectedOption.style.color === "#fff" ? "#007BFF" : "#fff";

        // Add or remove the selected item from the list
        const index = this._selectedAuthors.indexOf(selectedOption.value);
        if (index === -1) {
          this._selectedAuthors.push(selectedOption.text);
          this._selectedAuthorSlug.push(selectedOption.value);
        } else {
          this._selectedAuthors.splice(index, 1);
          this._selectedAuthorSlug.splice(index, 1);
        }

        // Update the selected author list
        selectedAuthorLabel.textContent = this._selectedAuthors.join(", ");
      }
    });

    // Add click event listener to update selected tags list
    tagSelect.addEventListener("click", (event) => {
      const selectedOption = event.target;

      if (selectedOption.tagName === "OPTION") {
        // Toggle the background color of the selected option
        selectedOption.style.backgroundColor =
          selectedOption.style.backgroundColor === "#007BFF"
            ? "#fff"
            : "#007BFF";

        // Toggle the text color of the selected option
        selectedOption.style.color =
          selectedOption.style.color === "#fff" ? "#007BFF" : "#fff";

        // Add or remove the selected item from the list
        const index = this._selectedTags.indexOf(selectedOption.value);
        if (index === -1) {
          this._selectedTags.push(selectedOption.value);
        } else {
          this._selectedTags.splice(index, 1);
        }

        // Update the selected tags input
        selectedTags.value = this._selectedTags.join(", ");
      }
    });

    // Add input event listener to update interval slider
    updateIntervalSlider.addEventListener("input", () => {
      updateIntervalLabel.textContent = updateIntervalSlider.value;
      this.intervalValue = updateIntervalSlider.value;
    });

    form.addEventListener("focusout", this.updateConfiguration.bind(this));
  }

  configChanged(newConfig) {
    // Update the local _config property with the new configuration
    this._config = newConfig;

    const event = new Event("config-changed", {
      bubbles: true,
      composed: true,
    });
    event.detail = { config: newConfig };
    this.dispatchEvent(event);
  }

  async searchAuthor(query) {
    try {
      // Convert the selected authors into a list in YAML format

      const searchData = {
        entity_id: this._config.entity,
        query: query,
      };

      const searchMessage = {
        domain: "quotable",
        service: "search_authors",
        type: "call_service",
        return_response: true,
        service_data: searchData,
      };

      const authorResponse = await this._hass.callWS(searchMessage);

      if (authorResponse && authorResponse.response) {
        console.log(authorResponse.response);
        const authorSelect = this.shadowRoot.getElementById("authorSelect");

        // Clear existing options
        authorSelect.innerHTML = "";
        this._authors = Object.keys(authorResponse.response).map((slug) => ({
          slug: slug,
          name: authorResponse.response[slug],
        }));
        // Add new options based on the author array
        this._authors.forEach((author) => {
          const option = document.createElement("option");
          option.value = author.slug;
          option.text = author.name;
          authorSelect.add(option);
        });
      }
    } catch (error) {
      console.error("Error searching author:", error);
    }
  }

  async updateConfiguration() {
    try {
      console.log("authorslug", this._selectedAuthorSlug);

      console.log("tag slug", this._selectedTags);

      const lowercaseTags = this._selectedTags.map((tag) => tag.toLowerCase());
      console.log("lowercase", lowercaseTags);

      const updateConfigData = {
        entity_id: this._config.entity,
        selected_tags: lowercaseTags,
        selected_authors: this._selectedAuthorSlug,
        update_frequency: parseInt(this.intervalValue) * 60,
      };

      const updateConfigMessage = {
        domain: "quotable",
        service: "update_configuration",
        type: "call_service",
        return_response: false,
        service_data: updateConfigData,
      };

      const responseUpdateConfig = await this._hass.callWS(updateConfigMessage);

      if (responseUpdateConfig) {
        console.error(" updating configuration:");
      }
    } catch (error) {
      console.error("Error updating configuration:", error);
    }
  }
}

customElements.define("quotable-card-editor", QuotableCardEditor);
