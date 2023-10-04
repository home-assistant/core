"""Remote platform for the jvc_projector integration."""

from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

from jvcprojector import const

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import JvcProjectorEntity

COMMANDS = {
    "menu": const.REMOTE_MENU,
    "up": const.REMOTE_UP,
    "down": const.REMOTE_DOWN,
    "left": const.REMOTE_LEFT,
    "right": const.REMOTE_RIGHT,
    "ok": const.REMOTE_OK,
    "back": const.REMOTE_BACK,
    "mpc": const.REMOTE_MPC,
    "hide": const.REMOTE_HIDE,
    "info": const.REMOTE_INFO,
    "input": const.REMOTE_INPUT,
    "cmd": const.REMOTE_CMD,
    "advanced_menu": const.REMOTE_ADVANCED_MENU,
    "picture_mode": const.REMOTE_PICTURE_MODE,
    "color_profile": const.REMOTE_COLOR_PROFILE,
    "lens_control": const.REMOTE_LENS_CONTROL,
    "setting_memory": const.REMOTE_SETTING_MEMORY,
    "gamma_settings": const.REMOTE_GAMMA_SETTINGS,
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the JVC Projector platform from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
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
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.device.power_off()
        await self.coordinator.async_refresh()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a remote command to the device."""
        for cmd in command:
            if cmd not in COMMANDS:
                raise HomeAssistantError(f"{cmd} is not a known command")
            _LOGGER.debug("Sending command '%s'", cmd)
            await self.device.remote(COMMANDS[cmd])
