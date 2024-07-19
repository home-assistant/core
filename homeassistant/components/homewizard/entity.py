"""Base entity for the HomeWizard integration."""

from __future__ import annotations

from homeassistant.const import ATTR_CONNECTIONS, ATTR_IDENTIFIERS, ATTR_MODEL
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HWEnergyDeviceUpdateCoordinator

TYPE_MODEL_MAP = {
    "HWE-P1": "Wi-Fi P1 Meter",
    "HWE-SKT": "Wi-Fi Energy Socket",
    "HWE-WTR": "Wi-Fi Water Meter",
    "HWE-KWH1": "Wi-Fi kWh Meter",
    "HWE-KWH3": "Wi-Fi kWh Meter",
    "SDM230-wifi": "Wi-Fi kWh Meter",
    "SDM630-wifi": "Wi-Fi kWh Meter",
}


class HomeWizardEntity(CoordinatorEntity[HWEnergyDeviceUpdateCoordinator]):
    """Defines a HomeWizard entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HWEnergyDeviceUpdateCoordinator) -> None:
        """Initialize the HomeWizard entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            manufacturer="HomeWizard",
            sw_version=coordinator.data.device.firmware_version,
            model_id=coordinator.data.device.product_type,
        )

        if product_type := coordinator.data.device.product_type:
            self._attr_device_info[ATTR_MODEL] = TYPE_MODEL_MAP.get(product_type)

        if (serial_number := coordinator.data.device.serial) is not None:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (CONNECTION_NETWORK_MAC, serial_number)
            }
            self._attr_device_info[ATTR_IDENTIFIERS] = {(DOMAIN, serial_number)}
