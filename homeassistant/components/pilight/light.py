"""Support for switching devices via Pilight to on and off."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_LIGHTS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_DIMLEVEL_MAX, CONF_DIMLEVEL_MIN
from .entity import SWITCHES_SCHEMA, PilightBaseDevice

LIGHTS_SCHEMA = SWITCHES_SCHEMA.extend(
    {
        vol.Optional(CONF_DIMLEVEL_MIN, default=0): cv.positive_int,
        vol.Optional(CONF_DIMLEVEL_MAX, default=15): cv.positive_int,
    }
)

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_LIGHTS): vol.Schema({cv.string: LIGHTS_SCHEMA})}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Pilight platform."""
    switches = config[CONF_LIGHTS]
    devices = []

    for dev_name, dev_config in switches.items():
        devices.append(PilightLight(hass, dev_name, dev_config))

    add_entities(devices)


class PilightLight(PilightBaseDevice, LightEntity):
    """Representation of a Pilight switch."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, hass, name, config):
        """Initialize a switch."""
        super().__init__(hass, name, config)
        self._dimlevel_min = config.get(CONF_DIMLEVEL_MIN)
        self._dimlevel_max = config.get(CONF_DIMLEVEL_MAX)

    @property
    def brightness(self):
        """Return the brightness."""
        return self._brightness

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on by calling pilight.send service with on code."""
        # Update brightness only if provided as an argument.
        # This will allow the switch to keep its previous brightness level.
        dimlevel = None

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

            # Calculate pilight brightness (as a range of 0 to 15)
            # By creating a percentage
            percentage = self._brightness / 255
            # Then calculate the dimmer range (aka amount
            # of available brightness steps).
            dimrange = self._dimlevel_max - self._dimlevel_min
            # Finally calculate the pilight brightness.
            # We add dimlevel_min back in to ensure the minimum is always reached.
            dimlevel = int(percentage * dimrange + self._dimlevel_min)

        self.set_state(turn_on=True, dimlevel=dimlevel)
