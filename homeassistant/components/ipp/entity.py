"""Entities for The Internet Printing Protocol (IPP) integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IPPDataUpdateCoordinator


class IPPEntity(CoordinatorEntity[IPPDataUpdateCoordinator]):
    """Defines a base IPP entity."""

    def __init__(
        self,
        device_id: str,
        coordinator: IPPDataUpdateCoordinator,
    ) -> None:
        """Initialize the IPP entity."""
        super().__init__(coordinator)
        self._device_id = device_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=self.coordinator.data.info.manufacturer,
            model=self.coordinator.data.info.model,
            name=self.coordinator.data.info.name,
            sw_version=self.coordinator.data.info.version,
            configuration_url=self.coordinator.data.info.more_info,
        )
