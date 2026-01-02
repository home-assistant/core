"""Defines base Prana entity."""

from dataclasses import dataclass
import logging

from homeassistant.components.switch import StrEnum
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    PranaConfigEntry,
    PranaCoordinator as PranaDataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PranaEntityDescription(EntityDescription):
    """Description for all Prana entities."""

    key: StrEnum


class PranaBaseEntity(CoordinatorEntity[PranaDataUpdateCoordinator]):
    """Defines a base Prana entity."""

    _attr_has_entity_name = True
    _attr_entity_description: PranaEntityDescription

    def __init__(
        self,
        entry: PranaConfigEntry,
        description: PranaEntityDescription,
    ) -> None:
        """Initialize the Prana entity."""
        super().__init__(entry.runtime_data)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},  # type: ignore[arg-type]
            manufacturer="Prana",
            name=self.coordinator.device_info.label,
            model=self.coordinator.device_info.pranaModel,
            serial_number=self.coordinator.device_info.manufactureId,
            sw_version=str(self.coordinator.device_info.fwVersion),
        )

        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        self.entity_description = description
