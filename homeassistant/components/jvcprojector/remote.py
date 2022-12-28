"""Remote platform for the JVC Projector integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jvcprojector import const

from homeassistant.components.remote import RemoteEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN as JVC_DOMAIN, POWER_ON, POWER_WARMING
from .entity import JvcProjectorEntity

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

ON_STATES = [POWER_ON, POWER_WARMING]

COMMANDS = {
    "menu": const.REMOTE_MENU,
    "up": const.REMOTE_MENU_UP,
    "down": const.REMOTE_MENU_DOWN,
    "left": const.REMOTE_MENU_LEFT,
    "right": const.REMOTE_MENU_RIGHT,
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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the JVC Projector platform from a config entry."""
    coordinator = hass.data[JVC_DOMAIN][entry.entry_id]
    entity = JvcProjectorRemote(coordinator)
    async_add_entities([entity], True)


class JvcProjectorRemote(JvcProjectorEntity, RemoteEntity):
    """Representation of a JVC Projector device."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.device.power_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.device.power_off()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a remote command to the device."""
        for cmd in command:
            if cmd not in COMMANDS:
                raise HomeAssistantError(f"{cmd} is not a known command")
            await self.device.remote(COMMANDS[cmd])

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.coordinator.data["power"] in ON_STATES
        super()._handle_coordinator_update()
