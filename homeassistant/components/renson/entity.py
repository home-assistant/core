"""Entity class for Renson ventilation unit."""
from __future__ import annotations

from renson_endura_delta.renson import RensonVentilation

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RensonCoordinator
from .const import DOMAIN


class RensonEntity(CoordinatorEntity):
    """Renson entity."""

    def __init__(
        self, name: str, api: RensonVentilation, coordinator: RensonCoordinator
    ) -> None:
        """Initialize the ComfoConnect fan."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "fan")},
            manufacturer="Renson",
            model=api.get_field_value(coordinator.data, "Device name"),
            name="Ventilation",
            sw_version=api.get_field_value(
                coordinator.data, "Firmware version"
            ).split()[-1],
            hw_version=api.get_field_value(coordinator.data, "Hardware version"),
        )

        self.api = api

        self._attr_unique_id = f"renson-{name}"
