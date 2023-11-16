class QuotableCard extends HTMLElement {
  constructor() {
    super();
    this.currentImageIndex = 0;
    this.imageUrls = [
      "https://cdn.pixabay.com/photo/2015/04/23/22/00/tree-736885_1280.jpg",
    ];
  }

  setConfig(config) {
    this._config = config;
  }

  set hass(hass) {
    if (!this.content) {
      this.innerHTML = `
                  <style>
                      ha-card {
                        position: relative;
                        overflow: hidden;
                        height: 200px;
                      }
                      .background-image {
                        width: 100%;
                        height: 100%;
                        background-size:     cover;
                        background-repeat:   no-repeat;
                        background-position: center center;
                      }

                      .overlay {
                        position: absolute;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                        align-items: center;
                        color: white;
                        text-align: center;
                      }

                      .quote {
                        font-size: 24px;
                        font-weight: bold;
                        margin-bottom: 16px;
                      }

                      .author {
                        font-size: 18px;
                        font-weight: bold;

                      }
                  </style>
                  <ha-card>
                      <img class="background-image" src="${
                        this.imageUrls[this.currentImageIndex]
                      }">
                      <div class="overlay">
                      <div class="quote">"Quote goes here"</div>
                      <div class="author">- Author Name</div>
                      </div>
                  </ha-card>
              `;
      this.content = this.querySelector(".background-image");
    }
  }

  getCardSize() {
    return 3;
  }

  static getStubConfig() {
    return { entity: "quotable.quotable" };
  }

  static getConfigElement() {
    return document.createElement("quotable-card-editor");
  }
}

class QuotableCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this._config = config;
    this.render();
  }

  render() {
    this.shadowRoot.innerHTML = `
    Multiselects and slider here
    `;
  }
}

customElements.define("quotable-card-editor", QuotableCardEditor);

customElements.define("quotable-card", QuotableCard);

//Add card to card picker in UI
window.customCards = window.customCards || [];
window.customCards.push({
  type: "quotable-card",
  name: "Quotable Card",
  preview: true,
  description: "Quotable",
});
