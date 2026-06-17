"""Entity class for Renson ventilation unit."""

from renson_endura_delta.field_enum import (
    DEVICE_NAME_FIELD,
    FIRMWARE_VERSION_FIELD,
    HARDWARE_VERSION_FIELD,
    MAC_ADDRESS,
)
from renson_endura_delta.renson import RensonVentilation

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RensonCoordinator


class RensonEntity(CoordinatorEntity[RensonCoordinator]):
    """Renson entity."""

    def __init__(
        self, name: str, api: RensonVentilation, coordinator: RensonCoordinator
    ) -> None:
        """Initialize the Renson entity."""
        super().__init__(coordinator)

        mac = api.get_field_value(coordinator.data, MAC_ADDRESS.name)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(CONNECTION_NETWORK_MAC, mac)},
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

        self._attr_unique_id = f"{mac}{name}"
