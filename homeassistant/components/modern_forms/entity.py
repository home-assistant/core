"""The Modern Forms integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ModernFormsDataUpdateCoordinator


class ModernFormsDeviceEntity(CoordinatorEntity[ModernFormsDataUpdateCoordinator]):
    """Defines a Modern Forms device entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: ModernFormsDataUpdateCoordinator,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the Modern Forms entity."""
        super().__init__(coordinator)
        self._attr_enabled_default = enabled_default
        self._entry_id = entry_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Modern Forms device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.info.mac_address)},
            name=self.coordinator.data.info.device_name,
            manufacturer="Modern Forms",
            model=self.coordinator.data.info.fan_type,
            sw_version=(
                f"{self.coordinator.data.info.firmware_version} /"
                f" {self.coordinator.data.info.main_mcu_firmware_version}"
            ),
        )
