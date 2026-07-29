"""Remote platform for Vizio SmartCast devices."""

import asyncio
from collections.abc import Iterable
from typing import Any, override

import voluptuous as vol

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import VizioConfigEntry
from .entity import VizioEntity
from .helpers import async_device_command

PARALLEL_UPDATES = 0

# Maps native vizaio key names to human-friendly aliases.
# Keys are uppercase native names (e.g. "CC_TOGGLE"), values are lists of lowercase aliases.
REMOTE_KEY_ALIASES: dict[str, list[str]] = {
    "CC_TOGGLE": ["closed_captions", "cc"],
    "CH_DOWN": ["channel_down"],
    "CH_PREV": ["previous_channel"],
    "CH_UP": ["channel_up"],
    "INPUT_NEXT": ["next_input"],
    "MUTE_TOGGLE": ["mute", "toggle_mute"],
    "OK": ["enter", "select"],
    "PIC_MODE": ["picture_mode"],
    "PIC_SIZE": ["picture_size"],
    "POW_OFF": ["off", "power_off"],
    "POW_ON": ["on", "power_on"],
    "POW_TOGGLE": ["power", "power_toggle", "toggle_power"],
    "SEEK_BACK": ["reverse", "rewind"],
    "SEEK_FWD": ["forward", "fast_forward", "ff"],
    "VOL_DOWN": ["volume_down"],
    "VOL_UP": ["volume_up"],
}

# Invert aliases into {alias: native_key} for O(1) lookup
_ALIAS_LOOKUP: dict[str, str] = {
    alias: key for key, aliases in REMOTE_KEY_ALIASES.items() for alias in aliases
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VizioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Vizio remote entity."""
    async_add_entities([VizioRemote(config_entry)])


class VizioRemote(VizioEntity, RemoteEntity):
    """Remote entity for Vizio SmartCast devices."""

    def __init__(self, config_entry: VizioConfigEntry) -> None:
        """Initialize the remote entity."""
        super().__init__(config_entry)
        valid_keys = set(self._device.available_keys)
        # Map lowercased native keys to their original uppercase vizaio names
        self._command_map: dict[str, str] = {key.lower(): key for key in valid_keys}
        # Add aliases only for native keys this device actually supports
        for alias, target in _ALIAS_LOOKUP.items():
            if target in valid_keys:
                self._command_map[alias] = target

    @property
    @override
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.coordinator.data.is_on

    def _resolve_command(self, command: str) -> str:
        """Resolve an lowercased command string to a vizaio key name."""
        if resolved := self._command_map.get(command):
            return resolved
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_command",
            translation_placeholders={"command": command},
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        await async_device_command(self._device.power_on())

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        await async_device_command(self._device.power_off())

    @override
    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send remote commands to the device."""
        num_repeats: int = kwargs.get(ATTR_NUM_REPEATS, 1)
        delay: float = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        resolved = [vol.All(vol.Lower, self._resolve_command)(cmd) for cmd in command]

        for i in range(num_repeats):
            for cmd in resolved:
                await async_device_command(self._device.send_key(cmd))
            if i < num_repeats - 1:
                await asyncio.sleep(delay)
