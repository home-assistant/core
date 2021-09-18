"""Support for Sure PetCare Flaps locks."""
from __future__ import annotations

import logging
from typing import Any, cast

from surepy.entities import SurepyEntity
from surepy.enums import EntityType, LockState
from surepy.exceptions import SurePetcareError

from homeassistant.components.lock import STATE_LOCKED, STATE_UNLOCKED, LockEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SurePetcareDataCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Sure PetCare locks on a config entry."""

    entities: list[SurePetcareLock] = []

    coordinator: SurePetcareDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    for surepy_entity in coordinator.data.values():
        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
        ]:

            for lock_state in (
                LockState.LOCKED_IN,
                LockState.LOCKED_OUT,
                LockState.LOCKED_ALL,
            ):
                entities.append(
                    SurePetcareLock(surepy_entity.id, coordinator, lock_state)
                )

    async_add_entities(entities)


class SurePetcareLock(CoordinatorEntity, LockEntity):
    """A lock implementation for Sure Petcare Entities."""

    def __init__(
        self, _id: int, coordinator: SurePetcareDataCoordinator, lock_state: LockState
    ) -> None:
        """Initialize a Sure Petcare lock."""
        super().__init__(coordinator)

        self._id = _id

        surepy_entity: SurepyEntity = coordinator.data[_id]

        _device_name = surepy_entity.type.name.capitalize().replace("_", " ")
        if surepy_entity.name:
            _device_name = f"{_device_name} {surepy_entity.name.capitalize()}"

        self._lock_state = lock_state.name.lower()
        self._attr_name = f"{_device_name} {self._lock_state.replace('_', ' ')}"
        self._attr_unique_id = f"{surepy_entity.household_id}-{_id}-{self._lock_state}"
        self._available = False

        self._update_attr(coordinator.data[_id])

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return self._available and super().available

    @callback
    def _update_attr(self, surepy_entity: SurepyEntity) -> None:
        """Update the state."""
        status = surepy_entity.raw_data()["status"]

        self._attr_is_locked = (
            LockState(status["locking"]["mode"]).name.lower() == self._lock_state
        )

        self._available = bool(status.get("online"))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and update the state."""
        self._update_attr(self.coordinator.data[self._id])
        self.async_write_ha_state()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        if self.state == STATE_LOCKED:
            return
        coordinator = cast(SurePetcareDataCoordinator, self.coordinator)
        try:
            await coordinator.lock_states[self._lock_state](self._id)
        except SurePetcareError:
            _LOGGER.error("Failed to lock %s", self.name)
            return
        self._attr_is_locked = True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        if self.state == STATE_UNLOCKED:
            return
        coordinator = cast(SurePetcareDataCoordinator, self.coordinator)
        try:
            await coordinator.surepy.sac.unlock(self._id)
        except SurePetcareError:
            _LOGGER.error("Failed to unlock %s", self.name)
            return
        self._attr_is_locked = False
        self.async_write_ha_state()
