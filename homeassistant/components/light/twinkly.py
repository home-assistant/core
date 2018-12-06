"""
Support for LEDWORKS Twinkly.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.twinkly/
"""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_HS_COLOR, PLATFORM_SCHEMA, SUPPORT_COLOR, Light)
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

REQUIREMENTS = ['xled==0.5.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'twinkly'

DEFAULT_NAME = "Twinkly Lights"

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
})

SUPPORT_TWINKLY = SUPPORT_COLOR


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up Twinkly lights."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if discovery_info is None:
        async_add_entities_config(hass, config, async_add_entities)


@callback
def async_add_entities_config(hass, config, async_add_entities):
    """Set up Twinkly lights configured within platform."""
    devices = []
    for device_id, device_config in config[CONF_DEVICES].items():
        host = device_config[CONF_HOST]
        _LOGGER.debug("Adding configured %s (host %s)", device_id, host)
        name = device_config.get(CONF_NAME)

        light = TwinklyLight(host, device_id, name)
        devices.append(light)
        hass.data[DOMAIN][name] = light
    async_add_entities(devices)


class TwinklyLight(Light):
    """Representation of an Twinkly lights."""

    def __init__(self, host, device_id, name=None):
        """Initialize the Twinkly lights."""
        import xled

        self._control = xled.control.HighControlInterface(host)
        self._state = None
        self._device_id = device_id
        if name:
            self._name = name
        else:
            self._name = device_id

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_TWINKLY

    @property
    def name(self):
        """Return a name for the device."""
        return self._name

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._device_id

    @property
    def is_on(self):
        """Return true if device is on."""
        return bool(self._state)

    def turn_on(self, **kwargs):
        """Turn the specified light on."""
        self._state = True

        if ATTR_HS_COLOR in kwargs:
            rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            self._control.set_static_color(*rgb)
        self._control.turn_on()

    def turn_off(self, **kwargs):
        """Turn the specified light off."""
        self._state = False
        self._control.turn_off()

    def update(self):
        """Synchronise internal state with the actual light state."""
        self._state = self._control.is_on()
