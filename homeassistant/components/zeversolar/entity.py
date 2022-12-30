"""Base Entity for Zeversolar sensors."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZeverSolarCoordinator


class ZeverSolarEntity(
    CoordinatorEntity[ZeverSolarCoordinator],
):
    """Defines a base ZeverSolar entity."""

    def __init__(
        self,
        *,
        device_id: str,
        coordinator: ZeverSolarCoordinator,
    ) -> None:
        """Initialize the ZeverSolar entity."""
        super().__init__(coordinator=coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name="ZeverSolar Sensor",
            manufacturer="ZeverSolar",
        )

    @property
    def available(self) -> bool:
        """Return device availability."""
        return super().available
