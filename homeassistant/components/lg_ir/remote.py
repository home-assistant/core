"""Remote platform for LG IR integration."""

from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.components.infrared import (
    DATA_COMPONENT,
    InfraredEntity,
    NECInfraredCommand,
    NECInfraredProtocol,
)
from homeassistant.components.remote import ATTR_HOLD_SECS, RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_INFRARED_ENTITY_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

LG_PROTOCOL = NECInfraredProtocol()
LG_ADDRESS = 0xFB04

# NEC protocol timing for hold duration calculation.
# Full command: 9ms header mark + 4.5ms header space + ~27ms data (32 bits avg) +
#               560us footer + 40ms idle = ~81ms
# Repeat code: 9ms mark + 2.25ms space + 560us mark + 40ms idle = ~52ms
# We use the repeat code duration since that's what's sent for held buttons.
NEC_REPEAT_DURATION_MS = 108


class LGCommand:
    """LG TV IR command codes."""

    BACK = 0xD728
    CHANNEL_DOWN = 0xFE01
    CHANNEL_UP = 0xFF00
    HOME = 0x837C
    INPUT = 0xF40B
    MENU = 0xBC43
    MUTE = 0xF609
    NAV_DOWN = 0xBE41
    NAV_LEFT = 0xF807
    NAV_RIGHT = 0xF906
    NAV_UP = 0xBF40
    NUM_0 = 0xEF10
    NUM_1 = 0xEE11
    NUM_2 = 0xED12
    NUM_3 = 0xEC13
    NUM_4 = 0xEB14
    NUM_5 = 0xEA15
    NUM_6 = 0xE916
    NUM_7 = 0xE817
    NUM_8 = 0xE718
    NUM_9 = 0xE619
    OK = 0xBB44
    POWER = 0xF708
    VOLUME_DOWN = 0xFC03
    VOLUME_UP = 0xFD02


COMMAND_MAP: dict[str, int] = {
    "power": LGCommand.POWER,
    "volume_up": LGCommand.VOLUME_UP,
    "volume_down": LGCommand.VOLUME_DOWN,
    "mute": LGCommand.MUTE,
    "channel_up": LGCommand.CHANNEL_UP,
    "channel_down": LGCommand.CHANNEL_DOWN,
    "up": LGCommand.NAV_UP,
    "down": LGCommand.NAV_DOWN,
    "left": LGCommand.NAV_LEFT,
    "right": LGCommand.NAV_RIGHT,
    "ok": LGCommand.OK,
    "back": LGCommand.BACK,
    "home": LGCommand.HOME,
    "menu": LGCommand.MENU,
    "input": LGCommand.INPUT,
    "0": LGCommand.NUM_0,
    "1": LGCommand.NUM_1,
    "2": LGCommand.NUM_2,
    "3": LGCommand.NUM_3,
    "4": LGCommand.NUM_4,
    "5": LGCommand.NUM_5,
    "6": LGCommand.NUM_6,
    "7": LGCommand.NUM_7,
    "8": LGCommand.NUM_8,
    "9": LGCommand.NUM_9,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LG IR remote from config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    async_add_entities([LgIrRemote(entry, infrared_entity_id)])


class LgIrRemote(RemoteEntity):
    """LG IR Remote entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: ConfigEntry, infrared_entity_id: str) -> None:
        """Initialize LG IR remote."""
        self._entry = entry
        self._infrared_entity_id = infrared_entity_id
        self._attr_unique_id = f"{entry.entry_id}_remote"
        self._attr_is_on = True  # Assume TV is on (IR is one-way)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="LG TV",
            manufacturer="LG",
            model="IR Remote",
        )

    def _get_infrared_entity(self) -> InfraredEntity | None:
        """Get the infrared entity."""
        component = self.hass.data.get(DATA_COMPONENT)
        if component is None:
            return None
        return component.get_entity(self._infrared_entity_id)

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Checks if the underlying IR entity is available.
        """
        entity = self._get_infrared_entity()
        return entity is not None and entity.available

    async def _send_command(self, command_code: int, repeat_count: int) -> None:
        """Send an IR command using the LG protocol."""
        entity = self._get_infrared_entity()
        if entity is None:
            _LOGGER.error("Infrared entity %s not found", self._infrared_entity_id)
            return

        command = NECInfraredCommand(
            address=LG_ADDRESS,
            command=command_code,
            protocol=LG_PROTOCOL,
            repeat_count=repeat_count,
        )
        await entity.async_send_command(command)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the TV."""
        await self._send_command(LGCommand.POWER, repeat_count=1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the TV."""
        await self._send_command(LGCommand.POWER, repeat_count=1)

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send IR commands by name.

        Supports the hold_secs parameter to simulate holding a button.
        The repeat count is calculated based on the NEC protocol timing.
        """
        hold_secs: float = kwargs.get(ATTR_HOLD_SECS, 0)

        if hold_secs > 0:
            repeat_count = max(1, int(hold_secs * 1000 / NEC_REPEAT_DURATION_MS))
        else:
            repeat_count = 1

        for cmd in command:
            cmd_lower = cmd.lower()
            if command_code := COMMAND_MAP.get(cmd_lower):
                await self._send_command(command_code, repeat_count)
            else:
                _LOGGER.warning("Unknown LG IR command: %s", cmd)
