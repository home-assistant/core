"""Support for LIFX lights."""
from __future__ import annotations

from aiolifx import products

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LIFXSensorUpdateCoordinator, LIFXUpdateCoordinator


class LIFXEntity(CoordinatorEntity[LIFXUpdateCoordinator]):
    """Representation of a LIFX entity with a coordinator."""

    def __init__(self, coordinator: LIFXUpdateCoordinator) -> None:
        """Initialise the light."""
        super().__init__(coordinator)
        self.bulb = coordinator.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial_number)},
            connections={(dr.CONNECTION_NETWORK_MAC, coordinator.mac_address)},
            manufacturer="LIFX",
            name=coordinator.label,
            model=products.product_map.get(self.bulb.product, "LIFX Bulb"),
            sw_version=self.bulb.host_firmware_version,
        )


class LIFXSensorEntity(CoordinatorEntity[LIFXSensorUpdateCoordinator]):
    """Representation of a LIFX sensor entity with a sensor coordinator."""

    def __init__(self, coordinator: LIFXSensorUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.bulb = coordinator.parent.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.parent.serial_number)},
            connections={(dr.CONNECTION_NETWORK_MAC, coordinator.parent.mac_address)},
            manufacturer="LIFX",
            name=coordinator.parent.label,
            model=products.product_map.get(self.bulb.product, "LIFX Bulb"),
            sw_version=self.bulb.host_firmware_version,
        )
