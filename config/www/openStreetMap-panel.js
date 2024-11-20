import "https://unpkg.com/wired-card@2.1.0/lib/wired-card.js?module";
import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

class OpenStreetMapPanel extends HTMLElement {
    set hass(hass) {
        // Create the card container
        if (!this.content) {
            this.content = document.createElement("hui-osm-card");
            this.appendChild(this.content);
        }

        // Pass configuration to the OSM card
        const config = {
            type: "custom:osm",
            auto_fit: true,
            entities: ["zone.home"],
        };
        this.content.setConfig(config);
        this.content.hass = hass;
    }
}

customElements.define("openstreetmap-panel", OpenStreetMapPanel);
