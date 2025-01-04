class WeatherActivitiesCard extends HTMLElement {
    set hass(hass) {
        const activities = hass.states['sensor.weather_activities'].attributes.activities || [];
        this.innerHTML = `
            <ha-card header="Weather Activities">
                <ul>
                    ${activities.map(activity => `<li>${activity}</li>`).join('')}
                </ul>
            </ha-card>
        `;
    }

    setConfig(config) {
        this.config = config;
    }

    getCardSize() {
        return 3;
    }
}

customElements.define('weather-activities-card', WeatherActivitiesCard);