class QuotableCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tags = [];
    this._authors = [];
    this._selectedItems = [];
  }

  set hass(hass) {
    this._hass = hass;
  }

  setConfig(config) {
    this._config = config;
    console.log(this._config); // Check if this._config is defined
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

      const message_author = {
        domain: "quotable",
        service: "fetch_all_authors",
        type: "call_service",
        return_response: true,
        service_data: serviceData,
      };

      // Call quotable service to fetch all tags
      const response_author = await this._hass.callWS(message_author);

      if (response_author && response_author.response) {
        // Update the _tags property with the fetched tags
        this._authors = Object.values(response_author.response);
        console.log(this._authors);
      }
    } catch (error) {
      console.error("Error fetching options:", error);
    }
    this.renderForm();
  }

  renderForm() {
    // Add the container to the shadow DOM
    this.shadowRoot.innerHTML = `
    <style>
      div {
        margin: 20px;
      }

      select[multiple] {
        width: 100%;
        height: 100px; /* Set a fixed height or adjust as needed */
        border: 1px solid #ccc;
        border-radius: 5px;
        background-color: #fff;
        padding: 5px;
        overflow-y: auto; /* Add vertical scrollbar if needed */
      }

      /* Style the multiselect options */
      option {
        padding: 5px;
        cursor: pointer;
      }

      /* Style the selected options */
      option:checked {
        background-color: #007BFF;
        color: #fff;
      }

      /* Style the slider input */
      input[type="range"] {
        width: 80%;
        height: 10px;
        border: 1px solid #ccc;
        border-radius: 5px;
        background-color: #fdd835;
        outline: none; /* Remove the default focus outline */
      }

      /* Style the slider thumb (handle) */
      input[type="range"]::-webkit-slider-thumb {
        -webkit-appearance: none; /* Remove the default appearance */
        width: 20px;
        height: 20px;
        background-color: #007BFF; /* Change the color of the thumb */
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
    <div>
    <label for="multiselect">Select Categories:</label>

      <input type="text" id="selectedTags" list="multiselect">
      <datalist id="multiselect" multiple value="Search..." autocomplete="on">
        ${this._authors
          .map((author) => `<option value="${author}">${author}</option>`)
          .join("")}
      </datalist>
    </div>
    <div>
    </div>
   `;

    // Add references to the input and multiselect elements
    const selectedAuthorsInput = this.shadowRoot.getElementById("selectedTags");
    const multiselect = this.shadowRoot.getElementById("multiselect");

    // Add click event listener to each option
    multiselect.addEventListener("click", (event) => {
      const selectedOptionAuthors = event.target;
      if (selectedOptionAuthors.AuthorName === "OPTION") {
        // Add or remove the selected item from the list
        const index = this._selectedItems.indexOf(selectedOptionAuthors.value);
        if (index === -1) {
          this._selectedItems.push(selectedOptionAuthors.value);
        } else {
          this._selectedItems.pop(selectedOptionAuthors.value);
        }
        // Update the selected author input
        selectedAuthorsInput.value = this._selectedItems.join(", ");
        // Add input event listener to update interval slider
      }
    });
  }
}

customElements.define("quotable-card-editor", QuotableCardEditor);
