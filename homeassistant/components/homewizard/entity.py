"""Base entity for the HomeWizard integration."""
from __future__ import annotations

from homeassistant.const import ATTR_IDENTIFIERS
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HWEnergyDeviceUpdateCoordinator


class HomeWizardEntity(CoordinatorEntity[HWEnergyDeviceUpdateCoordinator]):
    """Defines a HomeWizard entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HWEnergyDeviceUpdateCoordinator) -> None:
        """Initialize the HomeWizard entity."""
        super().__init__(coordinator=coordinator)
        self._attr_device_info = DeviceInfo(
            name=coordinator.entry.title,
            manufacturer="HomeWizard",
            sw_version=coordinator.data.device.firmware_version,
            model=coordinator.data.device.product_type,
        )

        if coordinator.data.device.serial is not None:
            self._attr_device_info[ATTR_IDENTIFIERS] = {
                (DOMAIN, coordinator.data.device.serial)
            }
