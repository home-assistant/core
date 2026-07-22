"""Base entities for Harbor."""

from typing import override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import HarborCoordinator


class HarborEntity(CoordinatorEntity[HarborCoordinator]):
    """Base Harbor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HarborCoordinator,
        unique_key: str,
    ) -> None:
        """Initialize the Harbor entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.data.serial}_{unique_key}"

    @override
    @property
    def available(self) -> bool:
        """Return if the entity is currently available."""
        if not self.coordinator.connected:
            return False
        return self.coordinator.data.last_seen is not None

    @override
    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info for the backing Harbor device."""
        return self.coordinator.device_info
