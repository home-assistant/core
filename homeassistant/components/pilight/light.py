"""Support for switching devices via Pilight to on and off."""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.const import CONF_LIGHTS
import homeassistant.helpers.config_validation as cv

from .base_class import SWITCHES_SCHEMA, PilightBaseDevice
from .const import CONF_DIMLEVEL_MAX, CONF_DIMLEVEL_MIN

_LOGGER = logging.getLogger(__name__)

LIGHTS_SCHEMA = SWITCHES_SCHEMA.extend(
    {
        vol.Optional(CONF_DIMLEVEL_MIN, default=0): cv.positive_int,
        vol.Optional(CONF_DIMLEVEL_MAX, default=15): cv.positive_int,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_LIGHTS): vol.Schema({cv.string: LIGHTS_SCHEMA})}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Pilight platform."""
    switches = config.get(CONF_LIGHTS)
    devices = []

    for dev_name, dev_config in switches.items():
        devices.append(PilightLight(hass, dev_name, dev_config))

    add_entities(devices)


class PilightLight(PilightBaseDevice, LightEntity):
    """Representation of a Pilight switch."""

    def __init__(self, hass, name, config):
        """Initialize a switch."""
        super().__init__(hass, name, config)
        self._dimlevel_min = config.get(CONF_DIMLEVEL_MIN)
        self._dimlevel_max = config.get(CONF_DIMLEVEL_MAX)

    @property
    def brightness(self):
        """Return the brightness."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    def turn_on(self, **kwargs):
        """Turn the switch on by calling pilight.send service with on code."""
        self._brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        dimlevel = int(self._brightness / (255 / self._dimlevel_max))

        self.set_state(turn_on=True, dimlevel=dimlevel)
