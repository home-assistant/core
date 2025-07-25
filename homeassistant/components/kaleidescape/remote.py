"""Sensor platform for Kaleidescape integration."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from kaleidescape import const as kaleidescape_const

from homeassistant.components.remote import RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KaleidescapeConfigEntry
from .entity import KaleidescapeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KaleidescapeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the platform from a config entry."""
    entities = [KaleidescapeRemote(entry.runtime_data)]
    async_add_entities(entities)


VALID_COMMANDS = {
    "select",
    "up",
    "down",
    "left",
    "right",
    "cancel",
    "replay",
    "scan_forward",
    "scan_reverse",
    "go_movie_covers",
    "menu_toggle",
}


class KaleidescapeRemote(KaleidescapeEntity, RemoteEntity):
    """Representation of a Kaleidescape device."""

    _attr_name = None

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device.power.state == kaleidescape_const.DEVICE_POWER_STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._device.leave_standby()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._device.enter_standby()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to a device."""
        for cmd in command:
            if cmd not in VALID_COMMANDS:
                raise HomeAssistantError(f"{cmd} is not a known command")
            await getattr(self._device, cmd)()
