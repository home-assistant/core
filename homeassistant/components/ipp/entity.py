"""Entities for The Internet Printing Protocol (IPP) integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IPPDataUpdateCoordinator


class IPPEntity(CoordinatorEntity[IPPDataUpdateCoordinator]):
    """Defines a base IPP entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IPPDataUpdateCoordinator,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the IPP entity."""
        super().__init__(coordinator)

        if description is not None:
            self.entity_description = description
            self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        else:
            self._attr_unique_id = coordinator.device_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer=self.coordinator.data.info.manufacturer,
            model=self.coordinator.data.info.model,
            name=self.coordinator.data.info.name,
            sw_version=self.coordinator.data.info.version,
            configuration_url=self.coordinator.data.info.more_info,
        )
