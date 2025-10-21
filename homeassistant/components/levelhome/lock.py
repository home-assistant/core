"""Lock platform for Level Lock."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DOMAIN,
)
from .coordinator import LevelLockDevice, LevelLocksCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Level Lock entities from a config entry."""
    data = (hass.data.get(DOMAIN) or {}).get(entry.entry_id) or {}
    coordinator: LevelLocksCoordinator = data["coordinator"]
    entities: list[LevelLockEntity] = [
        LevelLockEntity(coordinator, lock_id)
        for lock_id in coordinator.data.keys()
    ]
    async_add_entities(entities)


class LevelLockEntity(CoordinatorEntity, LockEntity):
    """Representation of a Level Lock device as a lock entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, LevelLockDevice]],
        lock_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._lock_id = lock_id
        device = self._device
        self._attr_unique_id = f"{DOMAIN}_{lock_id}"
        self._attr_name = device.name

    @property
    def _device(self) -> LevelLockDevice:
        return self.coordinator.data[self._lock_id]

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self._lock_id in self.coordinator.data
        )

    @property
    def is_locked(self) -> bool | None:
        return self._device.is_locked

    @property
    def is_locking(self) -> bool:
        """Return true if lock is locking."""
        state = self._device.state
        if state is None:
            return False
        return state.lower() == "locking"

    @property
    def is_unlocking(self) -> bool:
        """Return true if lock is unlocking."""
        state = self._device.state
        if state is None:
            return False
        return state.lower() == "unlocking"

    @property
    def device_info(self) -> DeviceInfo:
        device = self._device
        return DeviceInfo(
            identifiers={(DOMAIN, device.lock_id)},
            name=device.name,
            manufacturer="Level Home",
            model="Lock",
        )

    async def async_lock(self, **kwargs: Any) -> None:  # type: ignore[override]
        # Prevent command if already in a transitional state
        if self.is_locking or self.is_unlocking:
            _LOGGER.debug(
                "Lock %s is already in transitional state, ignoring lock command",
                self._lock_id,
            )
            return

        # Optimistically set transitional state immediately for UI responsiveness
        self._set_optimistic_state("locking")
        try:
            # Send command - actual state will come back via WebSocket push
            await self.coordinator.async_send_command(self._lock_id, "lock")
            # Note: We do NOT update to "locked" here - wait for WebSocket confirmation
        except Exception:
            # Revert optimistic state on failure
            await self.coordinator.async_request_refresh()
            raise

    async def async_unlock(self, **kwargs: Any) -> None:  # type: ignore[override]
        # Prevent command if already in a transitional state
        if self.is_locking or self.is_unlocking:
            _LOGGER.debug(
                "Lock %s is already in transitional state, ignoring unlock command",
                self._lock_id,
            )
            return

        # Optimistically set transitional state immediately for UI responsiveness
        self._set_optimistic_state("unlocking")
        try:
            # Send command - actual state will come back via WebSocket push
            await self.coordinator.async_send_command(self._lock_id, "unlock")
            # Note: We do NOT update to "unlocked" here - wait for WebSocket confirmation
        except Exception:
            # Revert optimistic state on failure
            await self.coordinator.async_request_refresh()
            raise

    def _set_optimistic_state(self, state: str) -> None:
        """Optimistically update the lock state before receiving confirmation.
        
        This sets the transitional state ("locking" or "unlocking") immediately
        for UI responsiveness. The actual final state will be received via 
        WebSocket push updates.
        """
        if self._lock_id in self.coordinator.data:
            # Create a copy of the data to update
            current_data = dict(self.coordinator.data)
            device = current_data[self._lock_id]
            # Update the device state to transitional state
            device.state = state
            device.is_locked = None  # Transitional states have None for is_locked
            # Update coordinator data without triggering a refresh
            self.coordinator.async_set_updated_data(current_data)
