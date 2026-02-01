"""Platform for sensor integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PhotoptimizerCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="energy_production_today",
        name="Energy production today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    SensorEntityDescription(
        key="energy_production_tomorrow",
        name="Energy production tomorrow",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    SensorEntityDescription(
        key="power_production_now",
        name="Power production now",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Photoptimizer sensor entities."""
    coordinator: PhotoptimizerCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        PhotoptimizerSensor(coordinator, entry, description)
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class PhotoptimizerSensor(CoordinatorEntity[PhotoptimizerCoordinator], SensorEntity):
    """Representation of a Photoptimizer sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PhotoptimizerCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        raw_estimate = (
            self.coordinator.data.get("raw", {}).get("forecast_solar")
            if isinstance(self.coordinator.data, dict)
            else None
        )
        if raw_estimate is None:
            return None

        key = self.entity_description.key

        if key == "energy_production_today":
            return getattr(raw_estimate, "energy_production_today", None)
        if key == "energy_production_tomorrow":
            return getattr(raw_estimate, "energy_production_tomorrow", None)
        if key == "power_production_now":
            return getattr(raw_estimate, "power_production_now", None)

        return None
