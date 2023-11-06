"""Support for EnOcean light sources."""
from __future__ import annotations

import math
from typing import Any

from enocean.utils import combine_hex
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .device import EnOceanEntity

CONF_SENDER_ID = "sender_id"

DEFAULT_NAME = "EnOcean Light"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ID, default=[]): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Required(CONF_SENDER_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(ATTR_BRIGHTNESS): cv.positive_int,
        vol.Optional(ATTR_COLOR_MODE): vol.In([ColorMode.BRIGHTNESS, ColorMode.ONOFF]),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the EnOcean light platform."""
    sender_id: list[int] = config[CONF_SENDER_ID]
    dev_name: str = config[CONF_NAME]
    dev_id: list[int] = config[CONF_ID]
    brightness = config.get(ATTR_BRIGHTNESS)
    color_mode = config.get(ATTR_COLOR_MODE)
    if color_mode == ColorMode.ONOFF:
        add_entities(
            [
                EnOceanLightNonDimmable(
                    sender_id, dev_id, dev_name, brightness, color_mode
                )
            ]
        )
    else:
        add_entities(
            [EnOceanLightDimmable(sender_id, dev_id, dev_name, brightness, color_mode)]
        )


class EnOceanLight(EnOceanEntity, LightEntity):
    """Representation of an EnOcean light source."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS, ColorMode.ONOFF}
    _attr_brightness = 50
    _attr_is_on = False

    def __init__(
        self,
        sender_id: list[int],
        dev_id: list[int],
        dev_name: str,
        brightness,
        color_mode,
    ) -> None:
        """Initialize the EnOcean light source."""
        super().__init__(dev_id)
        self._sender_id = sender_id
        self._attr_brightness = brightness or self._attr_brightness
        self._attr_color_mode = color_mode or self._attr_color_mode

        self._attr_unique_id = str(combine_hex(dev_id))
        self._attr_name = dev_name

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on light. Will send the provided command to Enocean relay."""
        self.send(kwargs.get("command"))
        self._attr_is_on = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off light. Will send the provided command to Enocean relay."""
        self.send(kwargs.get("command"))
        self._attr_is_on = False

    def send(self, command):
        """Get the GFVS command, extend with 00 and append a sender_id before sending."""
        command.extend(self._sender_id)
        command.extend([0x00])
        self.send_command(command, [], 0x01)


class EnOceanLightNonDimmable(EnOceanLight):
    """Representation of an EnOcean on/off light source."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_is_on = False

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light source on. Simulate GFVS command."""
        command = [0xA5, 0x01, 0x0, 0x00, 0x09]
        super().turn_on(command=command)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off on/off light."""
        command = [0xA5, 0x01, 0x00, 0x00, 0x08]
        super().turn_off(command=command)


class EnOceanLightDimmable(EnOceanLight):
    """Representation of a dimmable EnOcean light source."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS, ColorMode.ONOFF}
    _attr_brightness = 50
    _attr_is_on = False

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light source on. Simulate GFVS command."""
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            self._attr_brightness = brightness

        bval = math.floor(self._attr_brightness / 256.0 * 100.0)
        command = [0xA5, 0x02, bval, 0x01, 0x09]

        super().turn_on(command=command)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        command = [0xA5, 0x02, 0x00, 0x00, 0x08]
        super().turn_off(command=command)

    def value_changed(self, packet):
        """Update the internal state of this device.

        Dimmer devices like Eltako FUD61 send telegram in different RORGs.
        We only care about the 4BS (0xA5).
        """
        if packet.data[0] == 0xA5 and packet.data[1] == 0x02:
            val = packet.data[2]
            self._attr_brightness = math.floor(val / 100.0 * 256.0)
            self._attr_is_on = bool(val != 0)
            self.schedule_update_ha_state()
