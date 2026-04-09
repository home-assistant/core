"""Lock platform for Xthings Cloud."""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import XthingsCloudCoordinator
from .entity import XthingsCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lock platform."""
    coordinator: XthingsCloudCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        XthingsCloudLock(coordinator, device_id, device_data)
        for device_id, device_data in coordinator.data.items()
        if device_data.get("type") == "lock"
    ]
    async_add_entities(entities)


class XthingsCloudLock(XthingsCloudEntity, LockEntity):
    """Xthings Cloud lock entity."""

    @property
    def is_locked(self) -> bool | None:
        return self.device_data.get("status", {}).get("locked")

    @property
    def is_jammed(self) -> bool | None:
        return self.device_data.get("status", {}).get("jammed", False)

    async def async_lock(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_lock_lock(self._device_id)

    async def async_unlock(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_lock_unlock(self._device_id)
