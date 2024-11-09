"""Support for X10 lights."""

from __future__ import annotations

import logging
from subprocess import STDOUT, CalledProcessError, check_output
from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_DEVICES, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEVICES): vol.All(
            cv.ensure_list,
            [{vol.Required(CONF_ID): cv.string, vol.Required(CONF_NAME): cv.string}],
        )
    }
)


def x10_command(command):
    """Execute X10 command and check output."""
    return check_output(["heyu", *command.split(" ")], stderr=STDOUT)


def get_unit_status(code):
    """Get on/off status for given unit."""
    output = check_output(["heyu", "onstate", code])
    return int(output.decode("utf-8")[0])


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the x10 Light platform."""
    is_cm11a = True
    try:
        x10_command("info")
    except CalledProcessError as err:
        _LOGGER.warning("Assuming that the device is CM17A: %s", err.output)
        is_cm11a = False

    add_entities(X10Light(light, is_cm11a) for light in config[CONF_DEVICES])


class X10Light(LightEntity):
    """Representation of an X10 Light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, light, is_cm11a):
        """Initialize an X10 Light."""
        self._name = light["name"]
        self._id = light["id"]
        self._brightness = 0
        self._state = False
        self._is_cm11a = is_cm11a

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

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        if self._is_cm11a:
            x10_command(f"on {self._id}")
        else:
            x10_command(f"fon {self._id}")
        self._brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        self._state = True

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        if self._is_cm11a:
            x10_command(f"off {self._id}")
        else:
            x10_command(f"foff {self._id}")
        self._state = False

    def update(self) -> None:
        """Fetch update state."""
        if self._is_cm11a:
            self._state = bool(get_unit_status(self._id))
        else:
            # Not supported on CM17A
            pass
