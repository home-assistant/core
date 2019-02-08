"""
Support for VOC.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.volvooncall/

"""
import logging

from homeassistant.components.volvooncall import VolvoEntity, DATA_KEY

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Volvo sensors."""
    if discovery_info is None:
        return
    async_add_entities([VolvoSensor(hass.data[DATA_KEY], *discovery_info)])


class VolvoSensor(VolvoEntity):
    """Representation of a Volvo sensor."""

    @property
    def state(self):
        """Return the state."""
        return self.instrument.state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.instrument.unit
