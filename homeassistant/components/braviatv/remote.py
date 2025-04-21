"""Remote control support for Bravia TV."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import ATTR_NUM_REPEATS, RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BraviaTVConfigEntry
from .entity import BraviaTVEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BraviaTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bravia TV Remote from a config entry."""

    coordinator = config_entry.runtime_data
    unique_id = config_entry.unique_id
    assert unique_id is not None

    async_add_entities([BraviaTVRemote(coordinator, unique_id, config_entry.title)])


class BraviaTVRemote(BraviaTVEntity, RemoteEntity):
    """Representation of a Bravia TV Remote."""

    _attr_name = None

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.coordinator.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.coordinator.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.coordinator.async_turn_off()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to device."""
        repeats = kwargs[ATTR_NUM_REPEATS]
        await self.coordinator.async_send_command(command, repeats)
