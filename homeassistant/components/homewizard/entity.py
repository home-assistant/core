"""Base entity for the HomeWizard integration."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HWEnergyDeviceUpdateCoordinator


def create_main_device_info(
    coordinator: HWEnergyDeviceUpdateCoordinator,
) -> DeviceInfo:
    """Return the device info for the main HomeWizard device."""
    device_info = DeviceInfo(
        manufacturer="HomeWizard",
        sw_version=coordinator.data.device.firmware_version,
        model_id=coordinator.data.device.product_type,
        model=coordinator.data.device.model_name,
    )
    if (serial_number := coordinator.data.device.serial) is not None:
        device_info.connections = {(CONNECTION_NETWORK_MAC, serial_number)}
        device_info.identifiers = {(DOMAIN, serial_number)}
        device_info.serial_number = serial_number
    return device_info


class HomeWizardEntity(CoordinatorEntity[HWEnergyDeviceUpdateCoordinator]):
    """Defines a HomeWizard entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HWEnergyDeviceUpdateCoordinator) -> None:
        """Initialize the HomeWizard entity."""
        super().__init__(coordinator)
        self._attr_device_info = create_main_device_info(coordinator)
