class QuotableCard extends HTMLElement {
  constructor() {
    super();
    this.currentImageIndex = 0;
    this.imageUrls = ["https://via.placeholder.com/400x200.png"];
  }

  set hass(hass) {
    if (!this.content) {
      this.innerHTML = `
                <style>
                    ha-card {
                        position: relative;
                        overflow: hidden;
                        width: 400px; /* Set your preferred width */
                        height: 200px; /* Set your preferred height */
                    }

                    .background-image {
                        width: 100%;
                        height: 100%;
                        object-fit: cover;
                    }
                </style>
                <ha-card>
                    <img class="background-image" src="${
                      this.imageUrls[this.currentImageIndex]
                    }">
                    <div class="overlay"></div>
                </ha-card>
            `;
      this.content = this.querySelector(".background-image");
    }
  }

  setConfig(config) {}

  getCardSize() {
    return 3;
  }

  static getStubConfig() {
    return { entity: "quotable.quotable" };
  }
}

customElements.define("quotable-card", QuotableCard);
