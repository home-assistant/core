"""Base Entity for Zeversolar sensors."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZeversolarCoordinator


class ZeversolarEntity(
    CoordinatorEntity[ZeversolarCoordinator],
):
    """Defines a base Zeversolar entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: ZeversolarCoordinator,
    ) -> None:
        """Initialize the Zeversolar entity."""
        super().__init__(coordinator=coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.serial_number)},
            name="Zeversolar Sensor",
            manufacturer="Zeversolar",
        )
