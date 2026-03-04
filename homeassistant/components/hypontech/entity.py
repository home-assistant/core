"""Base entity for the Hypontech Cloud integration."""

from __future__ import annotations

from hyponcloud import PlantData

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HypontechDataCoordinator


class HypontechEntity(CoordinatorEntity[HypontechDataCoordinator]):
    """Base entity for Hypontech Cloud."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HypontechDataCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.account_id)},
            name="Overview",
            manufacturer="Hypontech",
        )


class HypontechPlantEntity(CoordinatorEntity[HypontechDataCoordinator]):
    """Base entity for Hypontech Cloud plant."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HypontechDataCoordinator, plant_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.plant_id = plant_id
        plant = coordinator.data.plants[plant_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, plant_id)},
            name=plant.plant_name,
            manufacturer="Hypontech",
        )

    @property
    def plant(self) -> PlantData:
        """Return the plant data."""
        return self.coordinator.data.plants[self.plant_id]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.plant_id in self.coordinator.data.plants
