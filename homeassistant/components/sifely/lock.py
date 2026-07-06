"""Lock platform for the Sifely smart lock integration."""

from __future__ import annotations

import logging
from typing import Any, override

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from pysifely import LOCK_STATE_LOCKED, LOCK_STATE_UNKNOWN, SifelyApiError
from .const import DOMAIN
from .coordinator import SifelyConfigEntry, SifelyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SifelyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sifely lock platform from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        SifelyLock(coordinator, lock_id) for lock_id in coordinator.data
    )


class SifelyLock(CoordinatorEntity[SifelyDataUpdateCoordinator], LockEntity):
    """Representation of a Sifely smart lock."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, coordinator: SifelyDataUpdateCoordinator, lock_id: int
    ) -> None:
        """Initialize the lock entity."""
        super().__init__(coordinator)
        self._lock_id = lock_id
        self._attr_unique_id = str(lock_id)

    @property
    def _data(self) -> dict[str, Any]:
        """Return this lock's coordinator data."""
        return self.coordinator.data.get(self._lock_id, {})

    @property
    def _info(self) -> dict[str, Any]:
        """Return the lock's KeyInfo structure."""
        return self._data.get("info", {})

    @property
    def _detail(self) -> dict[str, Any]:
        """Return the lock's LockDetailDTO structure."""
        return self._data.get("detail", {})

    @property
    @override
    def available(self) -> bool:
        """Return True if the lock is present in the latest update."""
        return super().available and self._lock_id in self.coordinator.data

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        info = self._info
        name = info.get("lockAlias") or info.get(
            "lockName", f"Sifely Lock {self._lock_id}"
        )
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._lock_id))},
            name=name,
            manufacturer="Sifely",
            model=info.get("lockName"),
            sw_version=self._detail.get("firmwareRevision"),
            hw_version=self._detail.get("hardwareRevision"),
        )

    @property
    @override
    def is_locked(self) -> bool | None:
        """Return whether the lock is locked."""
        state = self._data.get("state")
        if state is None or state == LOCK_STATE_UNKNOWN:
            return None
        return state == LOCK_STATE_LOCKED

    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        try:
            await self.coordinator.client.lock(self._lock_id)
        except SifelyApiError as err:
            raise HomeAssistantError(f"Failed to lock: {err}") from err
        await self.coordinator.async_request_refresh()

    @override
    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        try:
            await self.coordinator.client.unlock(self._lock_id)
        except SifelyApiError as err:
            raise HomeAssistantError(f"Failed to unlock: {err}") from err
        await self.coordinator.async_request_refresh()
