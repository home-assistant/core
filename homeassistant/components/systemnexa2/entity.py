"""Base entity for SystemNexa2 integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import SystemNexa2DataUpdateCoordinator


class SystemNexa2Entity(CoordinatorEntity[SystemNexa2DataUpdateCoordinator]):
    """Base entity class for SystemNexa2 devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SystemNexa2DataUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize the SystemNexa2 entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.data.unique_id}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.unique_id)},
            manufacturer=MANUFACTURER,
            name=coordinator.data.info_data.name,
            model=coordinator.data.info_data.model,
            sw_version=coordinator.data.info_data.sw_version,
            hw_version=str(coordinator.data.info_data.hw_version),
        )
