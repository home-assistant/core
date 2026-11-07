"""Shared BUSY Bar entity."""

from typing import cast

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BusyCoordinator


class BusyEntity(CoordinatorEntity[BusyCoordinator]):
    """An entity backed by BUSY Bar status."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: BusyCoordinator, description: EntityDescription
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        status = coordinator.data.status
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, cast(str, entry.unique_id))},
            name=entry.title,
            manufacturer="BUSY",
            model="BUSY Bar",
            serial_number=status.device.serial_number if status.device else None,
            hw_version=status.device.otp_model if status.device else None,
            sw_version=status.firmware.version if status.firmware else None,
            configuration_url=coordinator.client.base_url,
        )
