"""Support for LIFX lights."""
from __future__ import annotations

from aiolifx import products
from aiolifx.aiolifx import Light

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    LIFXLightUpdateCoordinator,
    LIFXSensorUpdateCoordinator,
    LIFXUpdateCoordinator,
)


class LIFXEntity(CoordinatorEntity[LIFXUpdateCoordinator]):
    """Representation of a LIFX entity with a coordinator."""

    def __init__(
        self, coordinator: LIFXLightUpdateCoordinator | LIFXSensorUpdateCoordinator
    ) -> None:
        """Initialise the light."""
        super().__init__(coordinator)
        self.device: Light = coordinator.device

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial_number)},
            connections={(dr.CONNECTION_NETWORK_MAC, coordinator.mac_address)},
            manufacturer="LIFX",
            name=coordinator.label,
            model=products.product_map.get(self.device.product, None),
            sw_version=self.device.host_firmware_version,
        )
