"""Platform for Schlage lock integration."""
from __future__ import annotations

from typing import Any

from pyschlage.lock import Lock

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import SchlageDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Schlage WiFi locks based on a config entry."""
    coordinator: SchlageDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        SchlageLockEntity(coordinator=coordinator, device_id=device_id)
        for device_id in coordinator.data.locks
    )


class SchlageLockEntity(CoordinatorEntity[SchlageDataUpdateCoordinator], LockEntity):
    """Schlage lock entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, coordinator: SchlageDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize a Schlage Lock."""
        super().__init__(coordinator=coordinator)
        self.device_id = device_id
        self._attr_unique_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=self._lock.name,
            manufacturer=MANUFACTURER,
            model=self._lock.model_name,
            sw_version=self._lock.firmware_version,
        )
        self._update_attrs()

    @property
    def _lock(self) -> Lock:
        """Fetch the Schlage lock from our coordinator."""
        return self.coordinator.data.locks[self.device_id]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # When is_locked is None the lock is unavailable.
        return super().available and self._lock.is_locked is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        return super()._handle_coordinator_update()

    def _update_attrs(self) -> None:
        """Update our internal state attributes."""
        self._attr_is_locked = self._lock.is_locked
        self._attr_is_jammed = self._lock.is_jammed

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        await self.hass.async_add_executor_job(self._lock.lock)
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        await self.hass.async_add_executor_job(self._lock.unlock)
        await self.coordinator.async_request_refresh()
