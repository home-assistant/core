"""Support for EnOcean light sources."""

from __future__ import annotations

import math
from typing import Any

from enocean.utils import combine_hex
import voluptuous as vol

from enocean.protocol.packet import RadioPacket, Packet
from enocean.protocol.constants import RORG

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entity import EnOceanEntity

CONF_SENDER_ID = "sender_id"
CONF_TYPE = "eltako_type"

DEFAULT_NAME = "EnOcean Light"

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ID, default=[]): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Required(CONF_SENDER_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_TYPE): cv.string,
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
    type: str = config[CONF_TYPE]

    add_entities([EnOceanLight(sender_id, dev_id, dev_name, type)])

class EnOceanLight(EnOceanEntity, LightEntity):
    """Representation of an EnOcean light source."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_brightness = 50
    _attr_is_on = False

    def __init__(self, sender_id: list[int], dev_id: list[int], dev_name: str, type: str) -> None:
        """Initialize the EnOcean light source."""
        super().__init__(dev_id)
        self._sender_id = sender_id
        self._attr_unique_id = str(combine_hex(dev_id))
        self._attr_name = dev_name
        self._destination_id = dev_id
        self._attr_type = type

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light source on or sets a specific dimmer value."""
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            self._attr_brightness = brightness

        bval = math.floor(self._attr_brightness / 256.0 * 64.0)
        if bval == 0:
            bval = 1

        if self._attr_type == "fl62":
            packet = RadioPacket.create(
                rorg=RORG.BS4,
                rorg_func=0x38,
                rorg_type=0x08,
                destination=self._destination_id,
                sender=self._sender_id,
                COM=1,
                command=1,
                DEL=0,
                LCK=0,
                SW=1)

        elif self._attr_type == "fd62":
            packet = RadioPacket.create(
                rorg=RORG.BS4,
                rorg_func=0x38,
                rorg_type=0x08,
                destination=self._destination_id,
                sender=self._sender_id,
                COM=2, # command id
                command=2, # command id
                LCK=0, # lock
                SW=1, # switching command
                STR=1, # store final value
                TIM=5, # Time in 1/10 seconds. 0 = no time specifed
                EDIMR=1, # 0: absolute, 1: relative
                RMP=128, # Ramping time in seconds, 0 = no ramping, 1...255 = seconds to 100%
                EDIM=bval) # Dimming value (absolute [0...255] or relative [0...100])

        self.send_packet(packet)

#        command = [0xA5, 0x02, bval, 0x01, 0x09]
#        command.extend(self._sender_id)
#        command.extend([0x00])
#        self.send_command(command, [], 0x01)
        self._attr_is_on = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light source off."""
        if self._attr_type == "fl62":
            packet = RadioPacket.create(
                rorg=RORG.BS4,
                rorg_func=0x38,
                rorg_type=0x08,
                destination=self._destination_id,
                sender=self._sender_id,
                COM=1,
                command=1,
                LCK=0,
                SW=0)
                                                                          
        elif self._attr_type == "fd62":
            packet = RadioPacket.create(
                rorg=RORG.BS4,
                rorg_func=0x38,
                rorg_type=0x08,
                destination=self._destination_id,
                sender=self._sender_id,
                COM=2,
                command=2,
                LCK=0,
                SW=0)
                                          
        self.send_packet(packet)

#        command = [0xA5, 0x02, 0x00, 0x01, 0x09]
#        command.extend(self._sender_id)
#        command.extend([0x00])
#        self.send_command(command, [], 0x01)
        self._attr_is_on = False

    def value_changed(self, packet):
        """Update the internal state of this device.

        Dimmer devices like Eltako FUD61 send telegram in different RORGs.
        We only care about the 4BS (0xA5).
        """
        if packet.data[0] == 0xA5 and packet.data[1] == 0x02:
            val = packet.data[2]
            self._attr_brightness = math.floor(val / 64.0 * 256.0)
            self._attr_is_on = bool(val != 0)
            self.schedule_update_ha_state()

        #_LOGGER.debug("enocean: Got message: %s",packet)
        if packet.data[0] == 0xF6:
            val = packet.data[1]
            self._attr_is_on = bool(val >= 0x70)
            self.schedule_update_ha_state()
