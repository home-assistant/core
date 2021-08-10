"""Support for Volvo On Call sensors."""
from homeassistant.components.sensor import SensorEntity

from . import DATA_KEY, VolvoEntity


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Volvo sensors."""
    if discovery_info is None:
        return
    async_add_entities([VolvoSensor(hass.data[DATA_KEY], *discovery_info)])


class VolvoSensor(VolvoEntity, SensorEntity):
    """Representation of a Volvo sensor."""

    @property
    def state(self):
        """Return the state."""
        return self.instrument.state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.instrument.unit
