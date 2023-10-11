"""Support for EnOcean light sources."""
from __future__ import annotations

from enum import Enum
import math
from typing import Any

from enocean.utils import combine_hex
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
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


class CentralCommandType(Enum):
    """Class to represent different central command types."""

    SWITCHING = 1
    DIMMING = 2


CONF_SENDER_ID = "sender_id"

CONF_COMMAND_TYPE = "command_type"

DEFAULT_NAME = "EnOcean Light"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ID, default=[]): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Required(CONF_SENDER_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(
            CONF_COMMAND_TYPE, default=CentralCommandType.DIMMING.name
        ): cv.enum(CentralCommandType),
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
    command_type: CentralCommandType = config[CONF_COMMAND_TYPE]

    add_entities([EnOceanLight(sender_id, dev_id, dev_name, command_type)])


class EnOceanLight(EnOceanEntity, LightEntity):
    """Representation of an EnOcean light source."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_brightness = 50
    _attr_is_on = False

    def __init__(
        self,
        sender_id: list[int],
        dev_id: list[int],
        dev_name: str,
        command_type: CentralCommandType,
    ) -> None:
        """Initialize the EnOcean light source."""
        super().__init__(dev_id)
        self._sender_id = sender_id
        self._attr_unique_id = str(combine_hex(dev_id))
        self._attr_name = dev_name
        self._command_type = command_type

    def __dimming_command_on(self, kwargs: Any) -> list[int]:
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            self._attr_brightness = brightness

        bval = math.floor(self._attr_brightness / 256.0 * 100.0)
        if bval == 0:
            bval = 128
        return [0xA5, 0x02, bval, 0x01, 0x09]

    def __switching_command_on(self, kwargs: Any) -> list[int]:
        return [0xA5, 0x01, 0x00, 0x00, 0x09]

    def __dimming_command_off(self) -> list[int]:
        return [0xA5, 0x02, 0x00, 0x00, 0x08]

    def __switching_command_off(self) -> list[int]:
        return [0xA5, 0x01, 0x00, 0x00, 0x08]

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light source on or sets a specific dimmer value."""
        match self._command_type:
            case CentralCommandType.SWITCHING:
                command = self.__switching_command_on(kwargs)
            case CentralCommandType.DIMMING:
                command = self.__dimming_command_on(kwargs)
        command.extend(self._sender_id)
        command.extend([0x00])
        self.send_command(command, [], 0x01)
        self._attr_is_on = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light source off."""
        match self._command_type:
            case CentralCommandType.SWITCHING:
                command = self.__switching_command_off()
            case CentralCommandType.DIMMING:
                command = self.__dimming_command_off()
        command.extend(self._sender_id)
        command.extend([0x00])
        self.send_command(command, [], 0x01)
        self._attr_is_on = False

    def value_changed(self, packet):
        """Update the internal state of this device.

        Dimmer devices like Eltako FUD61 send telegram in different RORGs.
        We only care about the 4BS (0xA5).

        Light switches like Eltako F4SR14-LED sends only on RORG RPS (0xF6)
        """
        if packet.data[0] == 0xA5 and packet.data[1] == 0x02:
            val = packet.data[2]
            onoff_val = packet.data[4]
            self._attr_brightness = math.floor(val / 100.0 * 256.0)
            self._attr_is_on = onoff_val == 0x09
            self.schedule_update_ha_state()
        elif packet.data[0] == 0xF6:
            val = packet.data[1]
            self._attr_is_on = val == 0x70
            self.schedule_update_ha_state()
