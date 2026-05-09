"""Locks for the Elke27 integration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import logging
from typing import TYPE_CHECKING, Any

from elke27_lib.errors import Elke27PinRequiredError

from homeassistant.components.lock import LockEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import Elke27DataUpdateCoordinator
from .entity import build_unique_id, device_info_for_entry, sanitize_name, unique_base

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .hub import Elke27Hub
    from .models import Elke27RuntimeData

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elke27 locks from a config entry."""
    data: Elke27RuntimeData | None = entry.runtime_data
    if data is None:
        _LOGGER.debug("Skipping lock setup because runtime data is missing")
        return
    hub = data.hub
    coordinator = data.coordinator
    known_ids: set[int] = set()

    def _async_add_locks() -> None:
        snapshot = coordinator.data
        if snapshot is None:
            _LOGGER.debug("Lock entities skipped because snapshot is unavailable")
            return
        entities: list[Elke27Lock] = []
        locks = list(_iter_locks(snapshot))
        if not locks:
            _LOGGER.debug("No locks available for entity creation")
            return
        for lock in locks:
            lock_id = getattr(lock, "lock_id", None)
            if not isinstance(lock_id, int):
                continue
            if lock_id in known_ids:
                continue
            known_ids.add(lock_id)
            entities.append(Elke27Lock(coordinator, hub, entry, lock_id, lock))
        if entities:
            async_add_entities(entities)

    _async_add_locks()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_locks))


class Elke27Lock(CoordinatorEntity[Elke27DataUpdateCoordinator], LockEntity):
    """Representation of an Elke27 lock."""

    _attr_has_entity_name = True
    _attr_translation_key = "lock"

    def __init__(
        self,
        coordinator: Elke27DataUpdateCoordinator,
        hub: Elke27Hub,
        entry: ConfigEntry,
        lock_id: int,
        lock: Any,
    ) -> None:
        """Initialize the lock entity."""
        super().__init__(coordinator)
        self._hub = hub
        self._lock_id = lock_id
        self._attr_name = (
            sanitize_name(getattr(lock, "name", None)) or f"Lock {lock_id}"
        )
        self._attr_unique_id = build_unique_id(
            unique_base(hub, coordinator, entry),
            "lock",
            lock_id,
        )
        self._attr_device_info = device_info_for_entry(hub, coordinator, entry)
        self._missing_logged = False

    @property
    def is_locked(self) -> bool | None:
        """Return if the lock is locked."""
        lock = _get_lock(self.coordinator.data, self._lock_id)
        if lock is None:
            self._log_missing()
            return None
        locked = getattr(lock, "locked", None)
        if isinstance(locked, bool):
            return locked
        status = getattr(lock, "status", None)
        if isinstance(status, str):
            normalized = status.strip().upper()
            if normalized in {"ON", "LOCKED"}:
                return True
            if normalized in {"OFF", "UNLOCKED"}:
                return False
        return None

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            self._hub.is_ready
            and _get_lock(self.coordinator.data, self._lock_id) is not None
        )

    async def async_lock(self, **_kwargs: Any) -> None:
        """Lock if supported by the client."""
        try:
            await self._hub.async_set_lock(self._lock_id, locked=True)
        except Elke27PinRequiredError as err:
            msg = "PIN required to perform this action."
            raise HomeAssistantError(msg) from err

    async def async_unlock(self, **_kwargs: Any) -> None:
        """Unlock if supported by the client."""
        try:
            await self._hub.async_set_lock(self._lock_id, locked=False)
        except Elke27PinRequiredError as err:
            msg = "PIN required to perform this action."
            raise HomeAssistantError(msg) from err

    def _log_missing(self) -> None:
        """Log when the lock snapshot is missing."""
        if self._missing_logged:
            return
        self._missing_logged = True
        _LOGGER.debug("Lock %s missing from snapshot", self._lock_id)


def _iter_locks(snapshot: Any) -> Iterable[Any]:
    locks = getattr(snapshot, "locks", None)
    if locks is None:
        return []
    if isinstance(locks, Mapping):
        return list(locks.values())
    if isinstance(locks, list | tuple):
        return locks
    return []


def _get_lock(snapshot: Any, lock_id: int) -> Any | None:
    for lock in _iter_locks(snapshot):
        if getattr(lock, "lock_id", None) == lock_id:
            return lock
    return None
