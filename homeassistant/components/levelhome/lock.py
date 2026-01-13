"""Lock platform for Level Lock."""

from __future__ import annotations

from dataclasses import replace
import logging
from typing import Any

from homeassistant.components import logbook, persistent_notification
from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LevelLockDevice, LevelLocksCoordinator

type LevelLockConfigEntry = ConfigEntry[LevelLocksCoordinator]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LevelLockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Level Lock entities from a config entry."""
    coordinator = entry.runtime_data
    lock_ids = list(coordinator.data.keys()) if coordinator.data else []
    _LOGGER.info("Setting up lock entities for %d devices: %s", len(lock_ids), lock_ids)
    entities: list[LevelLockEntity] = [
        LevelLockEntity(coordinator, lock_id) for lock_id in lock_ids
    ]
    async_add_entities(entities)

    def _add_new_devices(new_lock_ids: list[str]) -> None:
        """Add entities for newly discovered devices."""
        new_entities = [
            LevelLockEntity(coordinator, lock_id) for lock_id in new_lock_ids
        ]
        _LOGGER.info("Adding %d new lock entities: %s", len(new_entities), new_lock_ids)
        async_add_entities(new_entities)

    coordinator.register_new_device_callback(_add_new_devices)


class LevelLockEntity(CoordinatorEntity[LevelLocksCoordinator], LockEntity):
    """Representation of a Level Lock device as a lock entity."""

    _attr_has_entity_name = True
    coordinator: LevelLocksCoordinator

    def __init__(
        self,
        coordinator: LevelLocksCoordinator,
        lock_id: str,
    ) -> None:
        """Initialize the Level Lock entity."""
        super().__init__(coordinator)
        self._lock_id = lock_id
        self._attr_unique_id = f"{DOMAIN}_{lock_id}"
        self._attr_name = None
        self._previous_state: str | None = None

    @property
    def _device(self) -> LevelLockDevice:
        return self.coordinator.data[self._lock_id]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self._lock_id in self.coordinator.data
        )

    @property
    def is_locked(self) -> bool | None:
        """Return true if lock is locked."""
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
        """Return device information."""
        device = self._device
        return DeviceInfo(
            identifiers={(DOMAIN, device.lock_id)},
            name=device.name,
            manufacturer="Level Home",
            model="Lock",
        )

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        # Prevent command if already in a transitional state
        if self.is_locking or self.is_unlocking:
            _LOGGER.debug(
                "Lock %s is already in transitional state, ignoring lock command",
                self._lock_id,
            )
            return

        # Optimistically set transitional state immediately for UI responsiveness
        self._set_optimistic_state("locking")
        device_name = self._device.name
        try:
            # Send command - actual state will come back via WebSocket push
            await self.coordinator.async_send_command(self._lock_id, "lock")
        except Exception as err:
            # Revert optimistic state on failure
            await self.coordinator.async_request_refresh()
            error_msg = f"Failed to lock {device_name}: {err}"
            _LOGGER.error(error_msg)
            logbook.async_log_entry(
                self.hass,
                name=device_name,
                message=f"Lock command failed: {err}",
                domain=DOMAIN,
                entity_id=self.entity_id,
            )
            persistent_notification.async_create(
                self.hass,
                message=f"Failed to lock **{device_name}**: {err}",
                title="Lock command failed",
                notification_id=f"{DOMAIN}_{self._lock_id}_lock_error",
            )
            raise

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        # Prevent command if already in a transitional state
        if self.is_locking or self.is_unlocking:
            _LOGGER.debug(
                "Lock %s is already in transitional state, ignoring unlock command",
                self._lock_id,
            )
            return

        # Optimistically set transitional state immediately for UI responsiveness
        self._set_optimistic_state("unlocking")
        device_name = self._device.name
        try:
            # Send command - actual state will come back via WebSocket push
            await self.coordinator.async_send_command(self._lock_id, "unlock")
        except Exception as err:
            # Revert optimistic state on failure
            await self.coordinator.async_request_refresh()
            error_msg = f"Failed to unlock {device_name}: {err}"
            _LOGGER.error(error_msg)
            logbook.async_log_entry(
                self.hass,
                name=device_name,
                message=f"Unlock command failed: {err}",
                domain=DOMAIN,
                entity_id=self.entity_id,
            )
            persistent_notification.async_create(
                self.hass,
                message=f"Failed to unlock **{device_name}**: {err}",
                title="Lock command failed",
                notification_id=f"{DOMAIN}_{self._lock_id}_unlock_error",
            )
            raise

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()
        if self._lock_id not in self.coordinator.data:
            return
        current_state = self._device.state
        self._previous_state = current_state

    def _set_optimistic_state(self, state: str) -> None:
        """Optimistically update the lock state before receiving confirmation.

        This sets the transitional state ("locking" or "unlocking") immediately
        for UI responsiveness. The actual final state will be received via
        WebSocket push updates.
        """
        if self._lock_id in self.coordinator.data:
            current_data = dict(self.coordinator.data)
            device = current_data[self._lock_id]
            updated_device = replace(device, state=state)
            current_data[self._lock_id] = updated_device
            self.coordinator.async_set_updated_data(current_data)
            self._previous_state = state
