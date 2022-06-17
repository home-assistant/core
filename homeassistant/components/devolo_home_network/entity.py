"""Generic platform."""
from __future__ import annotations

from devolo_plc_api.device import Device

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class DevoloEntity(CoordinatorEntity):
    """Representation of a devolo home network device."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, device: Device, device_name: str
    ) -> None:
        """Initialize a devolo home network device."""
        super().__init__(coordinator)

        self.device = device

        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{device.ip}",
            identifiers={(DOMAIN, str(device.serial_number))},
            manufacturer="devolo",
            model=device.product,
            name=device_name,
            sw_version=device.firmware_version,
        )
        self._attr_unique_id = f"{device.serial_number}_{self.entity_description.key}"
