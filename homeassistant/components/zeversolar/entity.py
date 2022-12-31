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

    def __init__(
        self,
        *,
        device_id: str,
        coordinator: ZeversolarCoordinator,
    ) -> None:
        """Initialize the Zeversolar entity."""
        super().__init__(coordinator=coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name="Zeversolar Sensor",
            manufacturer="Zeversolar",
        )

