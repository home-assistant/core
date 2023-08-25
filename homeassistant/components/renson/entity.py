"""Entity class for Renson ventilation unit."""
from __future__ import annotations

from renson_endura_delta.field_enum import (
    DEVICE_NAME_FIELD,
    FIRMWARE_VERSION_FIELD,
    HARDWARE_VERSION_FIELD,
    MAC_ADDRESS,
)
from renson_endura_delta.renson import RensonVentilation

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RensonCoordinator
from .const import DOMAIN


class RensonEntity(CoordinatorEntity[RensonCoordinator]):
    """Renson entity."""

    def __init__(
        self, name: str, api: RensonVentilation, coordinator: RensonCoordinator
    ) -> None:
        """Initialize the Renson entity."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, api.get_field_value(coordinator.data, MAC_ADDRESS.name))
            },
            manufacturer="Renson",
            model=api.get_field_value(coordinator.data, DEVICE_NAME_FIELD.name),
            name="Ventilation",
            sw_version=api.get_field_value(
                coordinator.data, FIRMWARE_VERSION_FIELD.name
            ),
            hw_version=api.get_field_value(
                coordinator.data, HARDWARE_VERSION_FIELD.name
            ),
        )

        self.api = api

        self._attr_unique_id = (
            api.get_field_value(coordinator.data, MAC_ADDRESS.name) + f"{name}"
        )
