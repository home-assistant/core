"""Support for Sure PetCare Flaps locks."""

from __future__ import annotations

from typing import Any

from surepy.entities import SurepyEntity
from surepy.enums import EntityType, LockState as SurepyLockState

from homeassistant.components.lock import LockEntity, LockState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SurePetcareDataCoordinator
from .entity import SurePetcareEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sure PetCare locks on a config entry."""

    coordinator: SurePetcareDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SurePetcareLock(surepy_entity.id, coordinator, lock_state)
        for surepy_entity in coordinator.data.values()
        if surepy_entity.type in [EntityType.CAT_FLAP, EntityType.PET_FLAP]
        for lock_state in (
            SurepyLockState.LOCKED_IN,
            SurepyLockState.LOCKED_OUT,
            SurepyLockState.LOCKED_ALL,
        )
    )


class SurePetcareLock(SurePetcareEntity, LockEntity):
    """A lock implementation for Sure Petcare Entities."""

    def __init__(
        self,
        surepetcare_id: int,
        coordinator: SurePetcareDataCoordinator,
        lock_state: SurepyLockState,
    ) -> None:
        """Initialize a Sure Petcare lock."""
        self._lock_state = lock_state.name.lower()
        self._available = False

        super().__init__(surepetcare_id, coordinator)

        self._attr_name = f"{self._device_name} {self._lock_state.replace('_', ' ')}"
        self._attr_unique_id = f"{self._device_id}-{self._lock_state}"

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return self._available and super().available

    @callback
    def _update_attr(self, surepy_entity: SurepyEntity) -> None:
        """Update the state."""
        status = surepy_entity.raw_data()["status"]

        self._attr_is_locked = (
            SurepyLockState(status["locking"]["mode"]).name.lower() == self._lock_state
        )

        self._available = bool(status.get("online"))

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        if self.state != LockState.UNLOCKED:
            return
        self._attr_is_locking = True
        self.async_write_ha_state()

        try:
            await self.coordinator.lock_states_callbacks[self._lock_state](self._id)
            self._attr_is_locked = True
        finally:
            self._attr_is_locking = False
            self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        if self.state != LockState.LOCKED:
            return
        self._attr_is_unlocking = True
        self.async_write_ha_state()

        try:
            await self.coordinator.surepy.sac.unlock(self._id)
            self._attr_is_locked = False
        finally:
            self._attr_is_unlocking = False
            self.async_write_ha_state()
