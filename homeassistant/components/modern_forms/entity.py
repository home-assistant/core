"""The Modern Forms integration."""

from typing import override

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ModernFormsDataUpdateCoordinator


def strip_device_name_prefix(device_name: str, name: str) -> str:
    """Strip a leading device-name prefix from a vendor-set fixture name.

    Fixtures are commonly named "<device name> <role>" in the Modern Forms
    app (e.g. "Master Bedroom Uplight"), which would otherwise duplicate
    once HA's has_entity_name prepends the device name to build the
    friendly name.
    """
    if device_name and name.lower().startswith(device_name.lower()):
        stripped = name[len(device_name) :].lstrip(" -_")
        if stripped:
            return stripped
    return name


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
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information about this Modern Forms device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.info.mac_address)},
            connections={
                (CONNECTION_NETWORK_MAC, self.coordinator.data.info.mac_address)
            },
            name=self.coordinator.data.info.device_name,
            manufacturer="Modern Forms",
            model=self.coordinator.data.info.fan_type,
            sw_version=(
                f"{self.coordinator.data.info.firmware_version} /"
                f" {self.coordinator.data.info.main_mcu_firmware_version}"
            ),
        )
