from homeassistant.components.sensor import SensorEntity

ACTIVITIES = []

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities([WeatherActivitiesSensor(hass)])

class WeatherActivitiesSensor(SensorEntity):
    def __init__(self, hass):
        self.hass = hass
        self._name = "Weather Activities"
        self._state = "No activity"
        self._activities = []

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {"activities": self._activities}

    def update_activities(self, weather_state):
        """Update activities based on weather state."""
        self._activities = []
        if weather_state == "clear-night":
            activity = self.hass.states.get("input_text.activity_clear_night").state
            self._activities.append(activity)
        elif weather_state == "rainy":
            activity = self.hass.states.get("input_text.activity_rainy").state
            self._activities.append(activity)
        elif weather_state == "cloudy":
            activity = self.hass.states.get("input_text.activity_cloudy").state
            self._activities.append(activity)
        elif weather_state == "snowy":
            activity = self.hass.states.get("input_text.activity_snowy").state
            self._activities.append(activity)
        elif weather_state == "windy":
            activity = self.hass.states.get("input_text.activity_windy").state
            self._activities.append(activity)
        else:
            self._activities.append("No specific activity")

        self._state = ", ".join(self._activities)

    async def async_update(self):
        """Fetch the latest weather state and update activities."""
        weather_entity = self.hass.states.get("weather.forecast_spiti")
        if weather_entity:
            weather_state = weather_entity.state
            self.update_activities(weather_state)