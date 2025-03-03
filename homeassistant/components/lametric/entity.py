"""Base entity for the LaMetric integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaMetricDataUpdateCoordinator


class LaMetricEntity(CoordinatorEntity[LaMetricDataUpdateCoordinator]):
    """Defines a LaMetric entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LaMetricDataUpdateCoordinator) -> None:
        """Initialize the LaMetric entity."""
        super().__init__(coordinator=coordinator)
        self._attr_device_info = DeviceInfo(
            connections={
                (CONNECTION_NETWORK_MAC, format_mac(coordinator.data.wifi.mac))
            },
            identifiers={(DOMAIN, coordinator.data.serial_number)},
            manufacturer="LaMetric Inc.",
            model_id=coordinator.data.model,
            name=coordinator.data.name,
            sw_version=coordinator.data.os_version,
            serial_number=coordinator.data.serial_number,
        )
