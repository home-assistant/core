"""Imeon inverter base class for entities."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import InverterCoordinator

type InverterConfigEntry = ConfigEntry[InverterCoordinator]


@dataclass
class InverterEntity(CoordinatorEntity[InverterCoordinator]):
    """Common elements for all entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: InverterCoordinator,
        entry: InverterConfigEntry,
        entity_description: EntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._inverter = coordinator.api.inverter
        self.data_key = entity_description.key
        assert entry.unique_id
        self._attr_unique_id = f"{entry.unique_id}_{self.data_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name="Imeon inverter",
            manufacturer="Imeon Energy",
            model=self._inverter.get("inverter"),
            sw_version=self._inverter.get("software"),
            serial_number=self._inverter.get("serial"),
            configuration_url=self._inverter.get("url"),
        )
