"""mütesync binary sensor entities."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers import update_coordinator

from .const import DOMAIN

SENSORS = {
    "in_meeting": "In Meeting",
    "muted": "Muted",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the mütesync button."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [MuteStatus(coordinator, sensor_type) for sensor_type in SENSORS], True
    )


class MuteStatus(update_coordinator.CoordinatorEntity, BinarySensorEntity):
    """Mütesync binary sensors."""

    def __init__(self, coordinator, sensor_type):
        """Initialize our sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type

    @property
    def name(self):
        """Return the name of the sensor."""
        return SENSORS[self._sensor_type]

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return f"{self.coordinator.data['user-id']}-{self._sensor_type}"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self._sensor_type]

    @property
    def device_info(self):
        """Return the device info of the sensor."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.data["user-id"])},
            "name": "mutesync",
            "manufacturer": "mütesync",
            "model": "mutesync app",
            "entry_type": "service",
        }
