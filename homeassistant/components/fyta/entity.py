"""Entities for FYTA integration."""

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FytaCoordinator


class FytaCoordinatorEntity(CoordinatorEntity[FytaCoordinator]):
    """Base Fyta entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FytaCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the FytaCoordinator sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{entry.entry_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            manufacturer="Fyta",
            model="Controller",
            identifiers={(DOMAIN, coordinator.data.get("email"))},
            name="Fyta Coordinator ({})".format(coordinator.data.get("email")),
        )

        self.entity_description = description


class FytaPlantEntity(Entity):
    """Base Fyta entity."""

    _attr_has_entity_name = True
    coordinator: FytaCoordinator
    plant_id: int

    def __init__(
        self,
        coordinator: FytaCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
        plant_id: int,
    ) -> None:
        """Initialize the Fyta sensor."""
        self._attr_unique_id = f"{entry.entry_id}-{plant_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            manufacturer="Fyta",
            model="Plant",
            identifiers={(DOMAIN, str(plant_id))},
            name=coordinator.data.get(plant_id).get("name"),
            via_device=(DOMAIN, coordinator.data.get("email")),
            sw_version=coordinator.data.get(plant_id).get("sw_version"),
        )
        self.coordinator = coordinator
        self.entity_description = description
        self.plant_id = plant_id
