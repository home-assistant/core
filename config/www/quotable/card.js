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
    this.quotes = [];
    this.quoteIndex = 0;
  }

  set hass(hass) {
    this._hass = hass;

    if (this._hass) {
      this.updateQuoteAndAuthor();
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

        const newQuotes = JSON.parse(attributes.quotes) || [];

        if (newQuotes.length > 0) {
          this.quotes = newQuotes;
          const quote = this.quotes[this.quoteIndex].content;
          const author = this.quotes[this.quoteIndex].author;
          this.render(quote, author);
        } else {
          this.fetchNewQuote();
        }
      }
    } catch (error) {
      // Show a default quote if update error
      this.render(this.DEFAULT_QUOTE, this.DEFAULT_AUTHOR);
      console.log("error caought in update quote");
    } finally {
      this.updateInProgress = false;
    }
  }

  async fetchNewQuote() {
    try {
      const serviceData = {
        entity_id: this._config.entity,
      };

      // Call quotable service to fetch a new quote
      const response = await this._hass.callService(
        "quotable",
        "fetch_a_quote",
        serviceData
      );

      // Render the response directly
      this.render(response.content, response.author);
    } catch (error) {
      console.error("Error fetching new quotes:", error);
    }
  }
  //Uodate card content
  render(quote = this.DEFAULT_QUOTE, author = this.DEFAULT_AUTHOR) {
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

          .buttons {
            position: absolute;
            top: 8px;
            right: 8px;
            display: flex;
            gap: 8px;
          }

          .button {
            cursor: pointer;
            color: white;
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

          <div class="buttons">
            <ha-icon class="button previous" icon="mdi:arrow-left"></ha-icon>
            <ha-icon class="button next" icon="mdi:arrow-right"></ha-icon>
         </div>
        </ha-card>
      `;
    this.updateOverlay(quote, author);

    this.content = this.querySelector(".background-image");

    this.prevButton = this.querySelector(".previous");
    this.nextButton = this.querySelector(".next");

    this.prevButton.addEventListener("click", () => this.showPreviousQuote());
    this.nextButton.addEventListener("click", () => this.showNextQuote());
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

  showPreviousQuote() {
    this.quoteIndex =
      (this.quoteIndex - 1 + this.quotes.length) % this.quotes.length;
    const quote = this.quotes[this.quoteIndex].content;
    const author = this.quotes[this.quoteIndex].author;

    //Update quote on card
    this.updateOverlay(quote, author);
  }

  showNextQuote() {
    this.quoteIndex = (this.quoteIndex + 1) % this.quotes.length;
    const quote = this.quotes[this.quoteIndex].content;
    const author = this.quotes[this.quoteIndex].author;

    //Update quote on card
    this.updateOverlay(quote, author);
  }

  updateOverlay(quote, author) {
    const quoteElement = this.querySelector(".quote");
    const authorElement = this.querySelector(".author");

    quoteElement.textContent = quote;
    authorElement.textContent = `- ${author}`;
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
