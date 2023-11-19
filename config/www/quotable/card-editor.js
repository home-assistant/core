class QuotableCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this._config = config;
    this.renderForm();
  }

  renderForm() {
    this.shadowRoot.innerHTML = "Multiselects and slider here";
  }
}

customElements.define("quotable-card-editor", QuotableCardEditor);
