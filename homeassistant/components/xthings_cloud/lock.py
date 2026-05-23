"""Lock platform for Xthings Cloud."""

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import XthingsCloudConfigEntry
from .entity import XthingsCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XthingsCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lock platform."""
    coordinator = entry.runtime_data
    entities = [
        XthingsCloudLock(coordinator, device_id, device_data)
        for device_id, device_data in coordinator.data.items()
        if device_data["type"] == "lock"
    ]
    async_add_entities(entities)


class XthingsCloudLock(XthingsCloudEntity, LockEntity):
    """Xthings Cloud lock entity."""

    @property
    def is_locked(self) -> bool | None:
        """Return true if lock is locked."""
        return self.device_data["status"].get("locked")

    @property
    def is_jammed(self) -> bool | None:
        """Return true if lock is jammed."""
        return self.device_data["status"].get("jammed")

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        await self.coordinator.client.async_lock_lock(self._device_id)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        await self.coordinator.client.async_lock_unlock(self._device_id)
