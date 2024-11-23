"""Remote platform for the jvc_projector integration."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from jvcprojector import const

from homeassistant.components.remote import RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JVCConfigEntry
from .const import REMOTE_COMMANDS
from .entity import JvcProjectorEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: JVCConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the JVC Projector platform from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([JvcProjectorRemote(coordinator)], True)


class JvcProjectorRemote(JvcProjectorEntity, RemoteEntity):
    """Representation of a JVC Projector device."""

    _attr_name = None

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.coordinator.data["power"] in [const.ON, const.WARMING]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.device.power_on()
        await asyncio.sleep(1)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.device.power_off()
        await asyncio.sleep(1)
        await self.coordinator.async_refresh()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a remote command to the device."""
        _LOGGER.debug("Sending command '%s'", command)

        for cmd in command:
            _LOGGER.debug("Processing command '%s'", cmd)

            # Split command and value
            parts = cmd.split(",", 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid command format: {cmd}")

            cmd_name, value = parts
            cmd_name = cmd_name.strip().lower()
            value = value.strip()

            if cmd_name == "remote":
                if value not in REMOTE_COMMANDS:
                    raise ValueError(f"Unknown remote command: {value}")
                await self.device.remote(REMOTE_COMMANDS[value])
            else:
                await self.device.send_command(cmd_name, value)
