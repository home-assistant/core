"""Entities for FYTA integration."""

from fyta_cli.fyta_models import Plant

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FytaConfigEntry
from .const import DOMAIN
from .coordinator import FytaCoordinator


class FytaPlantEntity(CoordinatorEntity[FytaCoordinator]):
    """Base Fyta Plant entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FytaCoordinator,
        entry: FytaConfigEntry,
        description: EntityDescription,
        plant_id: int,
    ) -> None:
        """Initialize the Fyta sensor."""
        super().__init__(coordinator)

        self.plant_id = plant_id
        self._attr_unique_id = f"{entry.entry_id}-{plant_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            manufacturer="Fyta",
            model="Plant",
            identifiers={(DOMAIN, f"{entry.entry_id}-{plant_id}")},
            name=self.plant.name,
            sw_version=self.plant.sw_version,
        )
        self.entity_description = description

    @property
    def plant(self) -> Plant:
        """Get plant data."""
        return self.coordinator.data[self.plant_id]

    @property
    def available(self) -> bool:
        """Test if entity is available."""
        return super().available and self.plant_id in self.coordinator.data
