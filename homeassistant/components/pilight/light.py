"""Support for switching devices via Pilight to on and off."""
import logging

import voluptuous as vol

from homeassistant.components.light import PLATFORM_SCHEMA, Light, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS
from homeassistant.const import CONF_LIGHTS
import homeassistant.helpers.config_validation as cv

from .base_class import SWITCHES_SCHEMA, PilightBaseDevice

from .const import (
    CONF_DIMLEVEL_MIN,
    CONF_DIMLEVEL_MAX
)

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

    for dev_name, properties in switches.items():
        devices.append(
            PilightLight(
                hass,
                dev_name,
                properties
            )
        )

    add_entities(devices)



class PilightLight(PilightBaseDevice, Light):
    """Representation of a Pilight switch."""

    def __init__(self, hass, name, properties):
        """Initialize a switch."""
        super().__init__(hass, name, properties)
        self._brightness = 255
        self._dimlevel_min = properties.get(CONF_DIMLEVEL_MIN)
        self._dimlevel_max = properties.get(CONF_DIMLEVEL_MAX)

    @property
    def brightness(self):
        """Return the brightness"""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS
        
    def turn_on(self, **kwargs):
        """Turn the switch on by calling pilight.send service with on code."""
        self._brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        dimlevel = int(self._brightness / (255/self._dimlevel_max))

        self.set_state(turn_on=True, dimlevel=dimlevel)