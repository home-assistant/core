"""Defines base Prana entity."""

from dataclasses import dataclass

from homeassistant.components.switch import StrEnum
from homeassistant.const import CONF_MODEL, CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MANUFACTURE_ID, CONF_SW_VERSION, DOMAIN
from .coordinator import (
    PranaConfigEntry,
    PranaCoordinator as PranaDataUpdateCoordinator,
)


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
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, "Prana Device"),
            manufacturer="Prana",
            model=entry.data.get(CONF_MODEL, "Unknown Model"),
            serial_number=entry.data.get(CONF_MANUFACTURE_ID, "Unknown Serial"),
            sw_version=entry.data.get(CONF_SW_VERSION, "Unknown Version"),
        )
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        self.entity_description = description
        self.type_key = description.key
