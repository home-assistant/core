"""Entity classes for the Lektrico integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LektricoDeviceDataUpdateCoordinator
from .const import DOMAIN


class LektricoEntity(CoordinatorEntity[LektricoDeviceDataUpdateCoordinator]):
    """Define an Lektrico entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        device_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial_number)},
            model=coordinator.device_type.upper(),
            name=device_name,
            manufacturer="Lektrico",
            sw_version=coordinator.data["fw_version"],
            hw_version=coordinator.board_revision,
            serial_number=coordinator.serial_number,
        )
