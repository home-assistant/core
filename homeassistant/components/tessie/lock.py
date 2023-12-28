"""Lock platform for Tessie integration."""
from __future__ import annotations

from typing import Any

from tessie_api import lock, unlock

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TessieDataUpdateCoordinator
from .entity import TessieEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tessie sensor platform from a config entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(TessieLockEntity(coordinator) for coordinator in coordinators)


class TessieLockEntity(TessieEntity, LockEntity):
    """Lock entity for current charge."""

    _attr_name = None

    def __init__(
        self,
        coordinator: TessieDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "vehicle_state_locked")

    @property
    def is_locked(self) -> bool | None:
        """Return the state of the Lock."""
        return self._value

    async def async_lock(self, **kwargs: Any) -> None:
        """Set new value."""
        await self.run(lock)
        self.set((self.key, True))

    async def async_unlock(self, **kwargs: Any) -> None:
        """Set new value."""
        await self.run(unlock)
        self.set((self.key, False))
