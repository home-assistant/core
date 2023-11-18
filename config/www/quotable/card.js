class QuotableCard extends HTMLElement {
  constructor() {
    super();
    this.currentImageIndex = 0;
    this.imageUrls = [
      "https://cdn.pixabay.com/photo/2016/11/29/05/45/astronomy-1867616_1280.jpg",
    ];
    this.updateInProgress = false;
    this.DEFAULT_AUTHOR = "Quotable";
    this.DEFAULT_QUOTE =
      "Today is a gift, that's why they call it the present. Make the most of it!";
  }

  set hass(hass) {
    this._hass = hass;

    if (this._hass) {
      this.updateQuoteAndAuthor();
      this.addPopUp();
    }
  }

  setConfig(config) {
    this._config = config;
  }

  async updateQuoteAndAuthor() {
    // Update quote on card
    if (this.updateInProgress) {
      return;
    }

    this.updateInProgress = true;

    try {
      const entityState = this._hass.states[this._config.entity];

      // Check if the entity state and its attributes exist
      if (entityState && entityState.attributes) {
        const attributes = entityState.attributes;

        const quotes = JSON.parse(attributes.quotes) || [];

        // Use the first quote and author from the state attributes
        const quote =
          quotes.length > 0 ? quotes[0].content : this.DEFAULT_QUOTE;
        const author =
          quotes.length > 0 ? quotes[0].author : this.DEFAULT_AUTHOR;

        this.render(quote, author);
      }
    } catch (error) {
      this.render(this.DEFAULT_QUOTE, this.DEFAULT_AUTHOR);
    } finally {
      this.updateInProgress = false;
    }
  }

  //Uodate card content
  render(quote = this.DEFAULT_QUOTE, author = this.DEFAULT_AUTHOR) {
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
            background-size: cover;
            background-repeat: no-repeat;
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
            font-size: 18px;
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
            <div class="quote">${quote}</div>
            <div class="author">- ${author}</div>
          </div>
        </ha-card>
      `;
      this.content = this.querySelector(".background-image");
    }
  }

  addPopUp() {
    if (!this._clickListenerAdded) {
      this.addEventListener("click", () => {
        console.log("Clicked! Opening popup...");
        this._openPopup();
      });
      this._clickListenerAdded = true;
    }
  }

  _openPopup() {
    const popupData = {
      title: "Quotable settings",
      content: [
        //Pop up form elements go here
      ],
    };

    this._hass.callService("browser_mod", "popup", popupData);
  }

  getCardSize() {
    return 3;
  }

  static getStubConfig() {
    return { entity: "quotable.quotable" };
  }
}

customElements.define("quotable-card", QuotableCard);

//Add card to card picker with a preview
window.customCards = window.customCards || [];
window.customCards.push({
  type: "quotable-card",
  name: "Quotable Card",
  preview: true,
  description: "Quotable",
});
