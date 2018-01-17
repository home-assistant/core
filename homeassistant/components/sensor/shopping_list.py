"""
Support for Shopping List Component as a sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.shopping_list/
"""
import asyncio
import logging
import voluptuous as vol
from homeassistant.const import CONF_NAME, CONF_ICON
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity


DEPENDENCIES = ['shopping_list']
DEFAULT_NAME = 'shopping_list'
DEFAULT_ICON = 'mdi:cart'
DOMAIN = 'shopping_list'

ATTR_ITEMS = 'items'

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_ICON, default=DEFAULT_ICON): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up Shopping List Sensor."""
    name = config.get(CONF_NAME)
    icon = config.get(CONF_ICON)
    async_add_devices([ShoppingListSensor(hass, name, icon)])


class ShoppingListSensor(Entity):
    """Representation of a Shopping List sensor."""

    def __init__(self, hass, name, icon):
        """Initialize the sensor."""
        self.hass = hass
        self._name = name
        self._icon = icon
        self._items = []
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

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
        attrs[ATTR_ITEMS] = [item for item in self.hass.data[DOMAIN].items]
        return attrs
