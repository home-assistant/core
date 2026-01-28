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
        unique_entity_id: str,
        name: str | None = None,
    ) -> None:
        """Initialize the SystemNexa2 entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        if name:
            self._attr_name = name
        self._attr_unique_id = f"{coordinator.data.unique_id}-{unique_entity_id}"
        dev_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.unique_id)},
            manufacturer=MANUFACTURER,
            name=coordinator.data.info_data.name,
            model=coordinator.data.info_data.model,
            sw_version=coordinator.data.info_data.sw_version,
            hw_version=str(coordinator.data.info_data.hw_version),
        )
        self._attr_device_info = dev_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.data.available
