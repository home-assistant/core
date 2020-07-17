"""Platform for magichome light integration."""
import logging


from magichome import MagicHomeApi
from magichome.devices.light.MagicHomeLight import MagicHomeLight
from magichome.devices.switch.MagicHomeSwitch import MagicHomeSwitch
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, PLATFORM_SCHEMA, Light)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the MagicHome Light platform."""

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    magichome = MagicHomeApi()

    hub = magichome.magichom_hub(username, password)

    for light in hub.lights :
        add_entities(MagicHomeDevice(light))


class MagicHomeDevice(MagicHomeLight):
    """Representation of an MagicHome Light."""

    def __init__(self, light):
        """Initialize an MagicHome."""
        self._light = light
        self._name = light.obj_name
        self._state = None
        self._brightness = None

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        self._light.brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        self._light.turn_on()

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._light.turn_off()

    def update(self):
        """Fetch new state data for this light."""
        self._light.update()
        self._state = self._light.is_on()
        self._brightness = self._light.brightness