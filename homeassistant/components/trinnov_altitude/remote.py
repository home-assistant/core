"""Remote for Trinnov integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.remote import RemoteEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import TrinnovAltitudeEntity

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the platform from a config entry."""
    entities = [TrinnovAltitudeRemote(hass.data[DOMAIN][entry.entry_id])]
    async_add_entities(entities)


VALID_COMMANDS = {
    "select",
}


class TrinnovAltitudeRemote(TrinnovAltitudeEntity, RemoteEntity):
    """Representation of a Trinnov Altitude device."""

    _attr_name = None

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return True

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
