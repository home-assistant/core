class QuotableCard extends HTMLElement {
  constructor() {
    super();
    this.currentImageIndex = 0;
    this.updateInProgress = false;
    this.renderCalled = false;
    this.DEFAULT_AUTHOR = "Quotable";
    this.DEFAULT_QUOTE =
      "Today is a gift, that's why they call it the present. Make the most of it!";
    this.quotes = [];
    this.quoteIndex = 0;
    this._attributes = {};
    this._bgColor = "";
    this._textColor = "";
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

  // Update quote on card
  async updateQuoteAndAuthor() {
    if (this.updateInProgress) {
      return;
    }

    this.updateInProgress = true;

    try {
      const entityState = this._hass.states[this._config.entity];

      // Check if the entity state and its attributes exist
      if (entityState && entityState.attributes) {
        this._attributes = entityState.attributes;

        const newQuotes = JSON.parse(this._attributes.quotes) || [];
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
    } catch (error) {}
  }
  //Uodate card content
  render(quote = this.DEFAULT_QUOTE, author = this.DEFAULT_AUTHOR) {
    if (this.renderCalled) {
      this.updateOverlay(quote, author);
      return;
    }
    this.innerHTML = `
    <style>
      ha-card {
        position: relative;
        overflow: hidden;
        height: 200px;
      }
      .background-div {
        width: 100%;
        height: 100%;
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
      }
    </style>
    <ha-card>
      <div class="background-div"></div>
      <div class="overlay">
        <div class="quote">${quote}</div>
        <div class="author">- ${author}</div>
      </div>
      <div class="buttons">
        <ha-icon class="button previous" icon="mdi:arrow-left"></ha-icon>
        <ha-icon class="button next" icon="mdi:arrow-right"></ha-icon>
        <ha-icon class="button refresh" icon="mdi:refresh"></ha-icon>
      </div>
    </ha-card>
  `;

    //Add event listeners for buttons
    this.prevButton = this.querySelector(".previous");
    this.nextButton = this.querySelector(".next");
    this.refreshButton = this.querySelector(".refresh");

    this.prevButton.addEventListener("click", () => this.showPreviousQuote());
    this.nextButton.addEventListener("click", () => this.showNextQuote());
    this.refreshButton.addEventListener("click", () => this.refreshQuote());

    //renderCalled flag to prevent double render
    this.renderCalled = true;

    //Fetch colors from quotable states
    this._bgColor = this._attributes.styles.bg_color;
    this._textColor = this._attributes.styles.text_color;

    //Update background, button and text colors
    this.querySelector(".overlay").style.color = textColor;
    this.querySelector(".buttons").style.color = textColor;
    this.querySelector(".background-div").style.background = bgColor;
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

  refreshQuote() {
    this.fetchNewQuote();
  }

  updateOverlay(quote, author) {
    const quoteElement = this.querySelector(".quote");
    const authorElement = this.querySelector(".author");

    quoteElement.textContent = quote;
    authorElement.textContent = `- ${author}`;

    //Fetch colors from quotable states
    this._bgColor = this._attributes.styles.bg_color;
    this._textColor = this._attributes.styles.text_color;

    this.querySelector(".overlay").style.color = this._textColor;
    this.querySelector(".buttons").style.color = this._textColor;
    this.querySelector(".background-div").style.background = this._bgColor;
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
