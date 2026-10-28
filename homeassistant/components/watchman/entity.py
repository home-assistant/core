"""SENSiTEntity class."""

import logging
from typing import override

from connectsensor.analysis import TankData

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER, MODEL
from .coordinator import SENSiTConfigEntry, SENSiTDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


class SENSiTEntity(CoordinatorEntity[SENSiTDataUpdateCoordinator]):
    """Common entity behavior for Kingspan Watchman SENSiT sensors."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: SENSiTDataUpdateCoordinator,
        config_entry: SENSiTConfigEntry,
        serial_number: str,
        entity_description: EntityDescription,
    ) -> None:
        """Create a SENSiT entity and set minimum attributes."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self.config_entry = config_entry
        self.serial_number = serial_number

        tank = self.tank_data
        tank_name = (
            tank.name if tank.name and tank.name != "Unknown" else config_entry.title
        )
        self._attr_unique_id = f"sensit-{self.serial_number}-{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.serial_number)},
            serial_number=self.serial_number,
            model=MODEL,
            name=tank_name,
            manufacturer=MANUFACTURER,
        )
        self._attr_extra_state_attributes = {
            "attribution": ATTRIBUTION,
            "id": self.serial_number,
            "integration": DOMAIN,
        }

    @property
    def tank_data(self) -> TankData:
        """Dynamically fetch data by serial number."""
        # Coverage note: we should always find a tank matching the serial number
        # but we defend against this not being initialized yet
        for tank in self.coordinator.data:  # pragma: no branch
            if tank.serial_number == self.serial_number:
                return tank
        return TankData(serial_number=self.serial_number)  # pragma: no cover

    @property
    def last_reset(self) -> None:
        """Time sensor was initialized (returns None)."""
        return None

    @property
    @override
    def available(self) -> bool:
        """Returns True if the entity is available."""
        return super().available and any(
            tank.serial_number == self.serial_number for tank in self.coordinator.data
        )
