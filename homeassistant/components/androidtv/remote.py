"""Support for the AndroidTV remote."""
from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

from androidtv.constants import KEYS
from androidtv.setup_async import AndroidTVAsync, FireTVAsync

from homeassistant.components.remote import ATTR_NUM_REPEATS, RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ANDROID_DEV,
    ANDROID_DEV_OPT,
    CONF_TURN_OFF_COMMAND,
    CONF_TURN_ON_COMMAND,
    DOMAIN,
)
from .entity import AndroidTVEntity, adb_decorator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the AndroidTV remote from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    aftv: AndroidTVAsync | FireTVAsync = entry_data[ANDROID_DEV]
    async_add_entities([AndroidTVRemote(aftv=aftv, entry=entry, entry_data=entry_data)])


class AndroidTVRemote(AndroidTVEntity, RemoteEntity):
    """Device that sends commands to a AndroidTV."""

    _attr_name = None
    _attr_should_poll = False

    @adb_decorator()
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        options = self._entry_data[ANDROID_DEV_OPT]
        if turn_on_cmd := options.get(CONF_TURN_ON_COMMAND):
            await self.aftv.adb_shell(turn_on_cmd)
        else:
            await self.aftv.turn_on()

    @adb_decorator()
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        options = self._entry_data[ANDROID_DEV_OPT]
        if turn_off_cmd := options.get(CONF_TURN_OFF_COMMAND):
            await self.aftv.adb_shell(turn_off_cmd)
        else:
            await self.aftv.turn_off()

    @adb_decorator()
    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to a device."""

        num_repeats = kwargs[ATTR_NUM_REPEATS]
        command_list = []
        for cmd in command:
            if key := KEYS.get(cmd):
                command_list.append(f"input keyevent {key}")
            else:
                command_list.append(cmd)

        for _ in range(num_repeats):
            for cmd in command_list:
                try:
                    await self.aftv.adb_shell(cmd)
                except UnicodeDecodeError:
                    _LOGGER.error("Failed to send command %s", cmd)
