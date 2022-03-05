"""Kaleidescape remote."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kaleidescape import const as kaleidescape_const

from homeassistant.components.remote import RemoteEntity

from .const import DOMAIN as KALEIDESCAPE_DOMAIN, NAME as KALEIDESCAPE_NAME

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any

    from kaleidescape import Device as KaleidescapeDevice

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the platform from a config entry."""
    entities = [KaleidescapeRemote(hass.data[KALEIDESCAPE_DOMAIN][entry.entry_id])]
    async_add_entities(entities, True)


class KaleidescapeRemote(RemoteEntity):
    """Representation of a Kaleidescape device."""

    def __init__(self, device: KaleidescapeDevice) -> None:
        """Initialize remote."""
        self._device = device

    @property
    def unique_id(self) -> str:
        """Return a unique ID for device."""
        return self._device.serial_number

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return f"{KALEIDESCAPE_NAME} {self._device.system.friendly_name}"

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
        for single_command in command:
            if single_command == "select":
                await self._device.select()
            elif single_command == "up":
                await self._device.up()
            elif single_command == "down":
                await self._device.down()
            elif single_command == "left":
                await self._device.left()
            elif single_command == "right":
                await self._device.right()
            elif single_command == "cancel":
                await self._device.cancel()
            elif single_command == "replay":
                await self._device.replay()
            elif single_command == "scan_forward":
                await self._device.scan_forward()
            elif single_command == "scan_reverse":
                await self._device.scan_reverse()
            elif single_command == "go_movie_covers":
                await self._device.go_movie_covers()
            elif single_command == "menu_toggle":
                await self._device.menu_toggle()
