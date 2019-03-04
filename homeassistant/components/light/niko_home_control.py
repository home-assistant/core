"""
Support for Niko Home Control.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/light.niko_home_control/
"""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, PLATFORM_SCHEMA, Light)
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['niko-home-control==0.1.8']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Niko Home Control light platform."""
    import nikohomecontrol

    host = config[CONF_HOST]

    try:
        hub = nikohomecontrol.Hub({
            'ip': host,
            'port': 8000,
            'timeout': 20000,
            'events': True
        })
    except OSError as err:
        _LOGGER.error("Unable to access %s (%s)", host, err)
        raise PlatformNotReady

    add_entities(
        [NikoHomeControlLight(light, hub) for light in hub.list_actions()],
        True)


class NikoHomeControlLight(Light):
    """Representation of an Niko Light."""

    def __init__(self, light, nhc):
        """Set up the Niko Home Control light platform."""
        self._nhc = nhc
        self._light = light
        self._name = light.name
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
        self._state = self._light.is_on
