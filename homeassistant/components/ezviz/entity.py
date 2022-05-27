"""An abstract class common to all Ezviz entities."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import EzvizDataUpdateCoordinator


class EzvizEntity(CoordinatorEntity[EzvizDataUpdateCoordinator], Entity):
    """Generic entity encapsulating common features of Ezviz device."""

    def __init__(
        self,
        coordinator: EzvizDataUpdateCoordinator,
        serial: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._serial = serial
        self._camera_name = self.data["name"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer=MANUFACTURER,
            model=self.data["device_sub_category"],
            name=self.data["name"],
            sw_version=self.data["version"],
        )

    @property
    def data(self) -> dict[str, Any]:
        """Return coordinator data for this entity."""
        return self.coordinator.data[self._serial]
