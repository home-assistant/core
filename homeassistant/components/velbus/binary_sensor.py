"""Support for Velbus Binary Sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice

from .const import DOMAIN
from . import VelbusEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Velbus binary sensor based on config_entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    modules_data = hass.data[DOMAIN][entry.entry_id]["binary_sensor"]
    entities = []
    for address, channel in modules_data:
        module = cntrl.get_module(address)
        entities.append(VelbusBinarySensor(module, channel))
    async_add_entities(entities)


class VelbusBinarySensor(VelbusEntity, BinarySensorDevice):
    """Representation of a Velbus Binary Sensor."""

    @property
    def is_on(self):
        """Return true if the sensor is on."""
        return self._module.is_closed(self._channel)
