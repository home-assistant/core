"""Base entity for the wallbox integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CHARGER_CURRENT_VERSION_KEY,
    CHARGER_DATA_KEY,
    CHARGER_NAME_KEY,
    CHARGER_PART_NUMBER_KEY,
    CHARGER_SERIAL_NUMBER_KEY,
    CHARGER_SOFTWARE_KEY,
    DOMAIN,
)
from .coordinator import WallboxCoordinator


class WallboxEntity(CoordinatorEntity[WallboxCoordinator]):
    """Defines a base Wallbox entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Wallbox device."""
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self.coordinator.data[CHARGER_DATA_KEY][CHARGER_SERIAL_NUMBER_KEY],
                )
            },
            name=f"Wallbox {self.coordinator.data[CHARGER_NAME_KEY]}",
            manufacturer="Wallbox",
            model=self.coordinator.data[CHARGER_DATA_KEY][CHARGER_PART_NUMBER_KEY],
            sw_version=self.coordinator.data[CHARGER_DATA_KEY][CHARGER_SOFTWARE_KEY][
                CHARGER_CURRENT_VERSION_KEY
            ],
        )
