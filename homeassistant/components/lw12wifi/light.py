"""Support for Lagute LW-12 WiFi LED Controller."""

from __future__ import annotations

import logging
from typing import Any

import lw12
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)


DEFAULT_NAME = "LW-12 FC"
DEFAULT_PORT = 5000

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up LW-12 WiFi LED Controller platform."""
    # Assign configuration variables.
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    # Add devices
    lw12_light = lw12.LW12Controller(host, port)
    add_entities([LW12WiFi(name, lw12_light)])


class LW12WiFi(LightEntity):
    """LW-12 WiFi LED Controller."""

    _attr_color_mode = ColorMode.HS
    _attr_should_poll = False
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_supported_features = LightEntityFeature.EFFECT | LightEntityFeature.TRANSITION

    def __init__(self, name, lw12_light):
        """Initialise LW-12 WiFi LED Controller.

        :param name: Friendly name for this platform to use.
        :param lw12_light: Instance of the LW12 controller.
        """
        self._light = lw12_light
        self._name = name
        self._state = None
        self._effect = None
        self._rgb_color = [255, 255, 255]
        self._brightness = 255

    @property
    def name(self):
        """Return the display name of the controlled light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def hs_color(self):
        """Read back the hue-saturation of the light."""
        return color_util.color_RGB_to_hs(*self._rgb_color)

    @property
    def effect(self):
        """Return current light effect."""
        if self._effect is None:
            return None
        return self._effect.replace("_", " ").title()

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def effect_list(self):
        """Return a list of available effects.

        Use the Enum element name for display.
        """
        return [effect.name.replace("_", " ").title() for effect in lw12.LW12_EFFECT]

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return True

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        self._light.light_on()
        if ATTR_HS_COLOR in kwargs:
            self._rgb_color = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            self._light.set_color(*self._rgb_color)
            self._effect = None
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            brightness = int(self._brightness / 255 * 100)
            self._light.set_light_option(lw12.LW12_LIGHT.BRIGHTNESS, brightness)
        if ATTR_EFFECT in kwargs:
            self._effect = kwargs[ATTR_EFFECT].replace(" ", "_").upper()
            # Check if a known and supported effect was selected.
            if self._effect in [eff.name for eff in lw12.LW12_EFFECT]:
                # Selected effect is supported and will be applied.
                self._light.set_effect(lw12.LW12_EFFECT[self._effect])
            else:
                # Unknown effect was set, recover by disabling the effect
                # mode and log an error.
                _LOGGER.error("Unknown effect selected: %s", self._effect)
                self._effect = None
        if ATTR_TRANSITION in kwargs:
            transition_speed = int(kwargs[ATTR_TRANSITION])
            self._light.set_light_option(lw12.LW12_LIGHT.FLASH, transition_speed)
        self._state = True

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self._light.light_off()
        self._state = False
