"""Lock platform for the UniFi Access integration."""

from __future__ import annotations

from typing import Any

from unifi_access_api import ApiError, Door, DoorLockRelayStatus

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import UnifiAccessConfigEntry, UnifiAccessCoordinator
from .entity import UnifiAccessEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnifiAccessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up UniFi Access lock entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        UnifiAccessLockEntity(coordinator, door) for door in coordinator.data.values()
    )


class UnifiAccessLockEntity(UnifiAccessEntity, LockEntity):
    """Representation of a UniFi Access door lock."""

    _attr_name = None
    _attr_supported_features = LockEntityFeature.OPEN

    def __init__(
        self,
        coordinator: UnifiAccessCoordinator,
        door: Door,
    ) -> None:
        """Initialize the lock entity."""
        super().__init__(coordinator, door, "lock")

    @property
    def is_locked(self) -> bool:
        """Return true if the door is locked."""
        return self._door.door_lock_relay_status == DoorLockRelayStatus.LOCK

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the door (not supported by UniFi Access)."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="lock_not_supported",
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the door."""
        try:
            await self.coordinator.client.unlock_door(self._door_id)
        except ApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unlock_failed",
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_open(self, **kwargs: Any) -> None:
        """Open the door (same as unlock for UniFi Access)."""
        await self.async_unlock(**kwargs)
