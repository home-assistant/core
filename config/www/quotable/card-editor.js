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

      //Data payload that is transmitted as part of the service call
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
      
      //Message object used when calling quotable service
      const message = {
        domain: "quotable",
        service: "fetch_all_tags",
        type: "call_service",
        return_response: true,
        service_data: serviceData,
      };

      // Call quotable service to fetch all tags
      const response_author = await this._hass.callWS(message_author);

      if (response_author && response_author.response) {
        // Update the _tags property with the fetched tags
        this._authors = Object.values(response_author.response);

      const response = await this._hass.callWS(message);

      if (response && response.response) {
        // Update the _tags property with the fetched tags
        this._tags = Object.values(response.response);
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

      input[type="text"] {
        width: 100%;
        padding: 5px;
        margin-bottom: 10px;
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


      /* Style the slider thumb */
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
    <label for="authorselect">Select Authors:</label>
      <input type="text" id="selectedAuthors" list="multiselect">
      <datalist id="authorselect" multiple value="Search..." autocomplete="on">
        ${this._authors
          .map((author) => `<option value="${author}">${author}</option>`)
          .join("")}
      </datalist>
    </div>
    
    <div>
    <label for="multiselect">Select Categories:</label>
      <input type="text" id="selectedTags" readonly>
      <select id="multiselect" multiple>
        ${this._tags
          .map((tag) => `<option value="${tag}">${tag}</option>`)
          .join("")}
      </select>
    </div>

    <div>
    <label for="slider">Select Update Interval:</label>
      <input type="range" id="slider" min="0" max="100" value="50">
      <span id="updateIntervalLabel">50</span>
    </div>
   `;

    // Add references to the input and multiselect elements
    const selectedAuthorsInput = this.shadowRoot.getElementById("selectedAuthors");
    const authorSelect = this.shadowRoot.getElementById("authorselect");

    // Add click event listener to each option
    authorSelect.addEventListener("click", (event) => {
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
      }
    });
    const selectedTagsInput = this.shadowRoot.getElementById("selectedTags");
    const multiselect = this.shadowRoot.getElementById("multiselect");

    
    // Add references to the input and interval values
    const updateIntervalSlider = this.shadowRoot.getElementById("slider");
    const updateIntervalLabel = this.shadowRoot.getElementById(
      "updateIntervalLabel"
    );

    // Add click event listener to each option
    multiselect.addEventListener("click", (event) => {
      const selectedOption = event.target;

      if (selectedOption.tagName === "OPTION") {
        // Toggle the background color of the selected option
        selectedOption.style.backgroundColor =
          selectedOption.style.backgroundColor === "#007BFF" ? "" : "#007BFF";
        selectedOption.style.color =
          selectedOption.style.color === "#fff" ? "" : "#fff";

        // Add or remove the selected item from the list
        const index = this._selectedItems.indexOf(selectedOption.value);
        if (index === -1) {
          this._selectedItems.push(selectedOption.value);
        } else {
          this._selectedItems.splice(index, 1);
        }

        // Update the selected tags input
        selectedTagsInput.value = this._selectedItems.join(", ");
      }
    });

    // Add input event listener to update interval slider
    updateIntervalSlider.addEventListener("input", () => {
      updateIntervalLabel.textContent = updateIntervalSlider.value;
    });
  }
}

customElements.define("quotable-card-editor", QuotableCardEditor);
