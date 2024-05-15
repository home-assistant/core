"""Sensor for PSS BLE Scanner."""
from homeassistant.helpers.entity import Entity

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up PSS BLE Scanner sensor."""
    async_add_entities([PSSBLEScannerSensor()])

class PSSBLEScannerSensor(Entity):
    """Representation of a PSS BLE Scanner sensor."""

    def __init__(self):
        """Initialize the sensor."""
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "PSS BLE Scanner"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update_state(self, data):
        """Update the state with new data."""
        self._state = data
        self.async_write_ha_state()
