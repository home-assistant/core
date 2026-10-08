"""Shared entity behavior for Immich Frames."""

from typing import override

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ImmichFramesDataUpdateCoordinator


class ImmichFramesEntity(CoordinatorEntity[ImmichFramesDataUpdateCoordinator]):
    """Base entity for one configured frame."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ImmichFramesDataUpdateCoordinator, key: str
    ) -> None:
        """Initialize the shared entity fields."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_translation_key = key

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return the logical frame device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=self.coordinator.config_entry.title,
            manufacturer="Immich",
            model="Photo frame",
            configuration_url=self.coordinator.configuration_url,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def available(self) -> bool:
        """Return false until the coordinator has a current frame."""
        data = self.coordinator.current_data
        return (
            super().available
            and self.coordinator.parent_available
            and data is not None
            and data.connected
            and data.status == "ready"
        )

    @override
    async def async_update(self) -> None:
        """Refresh the coordinator and invalidate its candidate index."""
        await self.coordinator.async_refresh_now()
