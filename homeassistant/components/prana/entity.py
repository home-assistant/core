"""Defines base Prana entity."""

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from homeassistant.components.switch import StrEnum
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PranaCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PranaEntityDescription(EntityDescription):
    """Description for all Prana entities."""

    key: StrEnum


class PranaBaseEntity(CoordinatorEntity[PranaCoordinator]):
    """Defines a base Prana entity."""

    _attr_has_entity_name = True
    _attr_entity_description: PranaEntityDescription

    def __init__(
        self,
        coordinator: PranaCoordinator,
        description: PranaEntityDescription,
    ) -> None:
        """Initialize the Prana entity."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
            manufacturer="Prana",
            name=coordinator.device_info.label,
            model=coordinator.device_info.pranaModel,
            serial_number=coordinator.device_info.manufactureId,
            sw_version=str(coordinator.device_info.fwVersion),
        )
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"
        self.entity_description = description
