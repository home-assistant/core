"""Base Entity for Roku."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RokuDataUpdateCoordinator
from .const import DOMAIN


class RokuEntity(CoordinatorEntity):
    """Defines a base Roku entity."""

    coordinator: RokuDataUpdateCoordinator

    def __init__(
        self, *, device_id: str, coordinator: RokuDataUpdateCoordinator
    ) -> None:
        """Initialize the Roku entity."""
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Roku device."""
        if self._device_id is None:
            return None

        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self.coordinator.data.info.name,
            manufacturer=self.coordinator.data.info.brand,
            model=self.coordinator.data.info.model_name,
            sw_version=self.coordinator.data.info.version,
            suggested_area=self.coordinator.data.info.device_location,
        )
