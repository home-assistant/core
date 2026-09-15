"""OpenGarage opener lock."""

from asyncio import Lock
from typing import Any, cast, override

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OpenGarageConfigEntry, OpenGarageDataUpdateCoordinator
from .entity import OpenGarageCapabilityEntity, async_add_capability_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenGarageConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the opener lock when supported."""
    async_add_capability_entities(
        entry.runtime_data,
        async_add_entities,
        {
            "lock_control": lambda: OpenGarageLock(
                entry.runtime_data,
                cast(str, entry.unique_id),
                EntityDescription(key="lock", translation_key="lock"),
            )
        },
    )


class OpenGarageLock(OpenGarageCapabilityEntity, LockEntity):
    """Representation of the opener's remote-control lock."""

    capability = "lock_control"

    def __init__(
        self,
        coordinator: OpenGarageDataUpdateCoordinator,
        device_id: str,
        description: EntityDescription,
    ) -> None:
        """Serialize the library's read-before-toggle lock operations."""
        self._command_lock = Lock()
        super().__init__(coordinator, device_id, description)

    @callback
    @override
    def _update_attr(self) -> None:
        """Update the reported lock state."""
        self._attr_is_locked = self.coordinator.data.lock_engaged

    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Engage the opener lock."""
        await self._async_set_lock(True)

    @override
    async def async_unlock(self, **kwargs: Any) -> None:
        """Disengage the opener lock."""
        await self._async_set_lock(False)

    async def _async_set_lock(self, engaged: bool) -> None:
        """Set the lock and refresh its reported state."""
        async with self._command_lock:
            await self.coordinator.async_command(
                lambda: self.coordinator.open_garage_connection.set_lock(engaged),
                allow_noop=True,
            )
            await self.coordinator.async_request_refresh()
