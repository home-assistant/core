"""
Support for Shopping List Component as a sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/shopping_list/
"""
import asyncio
import logging
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['shopping_list']
DOMAIN = 'shopping_list'

ATTR_LIST = 'list'

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up Shopping List Sensor."""
    dev = []
    dev.append(ShoppingListSensor(hass))
    async_add_devices(dev, True)


class ShoppingListSensor(Entity):
    """Representation of a Shopping List sensor."""

    def __init__(self, hass):
        """Initialize the sensor."""
        self.hass = hass
        self._name = 'Shopping List'
        self._list = []
        self._state = 'unknown'

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.hass.data[DOMAIN].items:
            return 'not_empty'
        return 'empty'

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attrs = {}
        attrs[ATTR_LIST] = [item for item in self.hass.data[DOMAIN].items]
        return attrs
