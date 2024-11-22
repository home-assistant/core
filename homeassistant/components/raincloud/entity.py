"""Support for Melnor RainCloud sprinkler water timer."""

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import SIGNAL_UPDATE_RAINCLOUD

KEY_MAP = {
    "auto_watering": "Automatic Watering",
    "battery": "Battery",
    "is_watering": "Watering",
    "manual_watering": "Manual Watering",
    "next_cycle": "Next Cycle",
    "rain_delay": "Rain Delay",
    "status": "Status",
    "watering_time": "Remaining Watering Time",
}

ICON_MAP = {
    "auto_watering": "mdi:autorenew",
    "battery": "",
    "is_watering": "",
    "manual_watering": "mdi:water-pump",
    "next_cycle": "mdi:calendar-clock",
    "rain_delay": "mdi:weather-rainy",
    "status": "",
    "watering_time": "mdi:water-pump",
}


class RainCloudEntity(Entity):
    """Entity class for RainCloud devices."""

    _attr_attribution = "Data provided by Melnor Aquatimer.com"

    def __init__(self, data, sensor_type):
        """Initialize the RainCloud entity."""
        self.data = data
        self._sensor_type = sensor_type
        self._name = f"{self.data.name} {KEY_MAP.get(self._sensor_type)}"
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_RAINCLOUD, self._update_callback
            )
        )

    def _update_callback(self):
        """Call update method."""
        self.schedule_update_ha_state(True)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"identifier": self.data.serial}

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON_MAP.get(self._sensor_type)
