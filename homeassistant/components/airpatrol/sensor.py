"""Support for AirPatrol sensors."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AirPatrolConfigEntry
from .coordinator import AirPatrolDataUpdateCoordinator

PARALLEL_UPDATES = 0


_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key="status",
        translation_key="status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirPatrolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AirPatrol sensors based on a config entry."""
    coordinator = entry.runtime_data

    # Get units from the API
    units = await coordinator.api.get_data()

    # Create sensors for each unit
    entities: list[SensorEntity] = []
    for unit in units:
        unit_id = unit["unit_id"]
        entities.extend(
            AirPatrolSensor(coordinator, description, unit, unit_id)
            for description in SENSOR_DESCRIPTIONS
        )

    async_add_entities(entities)


class AirPatrolSensor(CoordinatorEntity[AirPatrolDataUpdateCoordinator], SensorEntity):
    """Representation of an AirPatrol sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirPatrolDataUpdateCoordinator,
        description: SensorEntityDescription,
        unit: dict[str, Any],
        unit_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.unit = unit
        self.unit_id = unit_id
        self._unavailable_logged = False
        # Set unique ID to include unit ID
        self._attr_unique_id = (
            f"{coordinator.api.get_unique_id()}_{unit_id}_{description.key}"
        )
        # Set device info for this unit
        self._attr_device_info = DeviceInfo(
            identifiers={("airpatrol", unit_id)},
            name=unit.get("name", f"AirPatrol Unit {unit_id}"),
            manufacturer=unit.get("manufacturer", "AirPatrol"),
            model=unit.get("model", "AirPatrol Unit"),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        is_available = (
            super().available
            and self.coordinator.data is not None
            and self.get_unit_data() is not None
        )
        if not is_available:
            if not self._unavailable_logged:
                _LOGGER.info(
                    "The sensor entity '%s' is unavailable", self._attr_unique_id
                )
                self._unavailable_logged = True
        elif self._unavailable_logged:
            _LOGGER.info("The sensor entity '%s' is back online", self._attr_unique_id)
            self._unavailable_logged = False
        return is_available

    def get_unit_data(self) -> dict[str, Any] | None:
        """Get the unit data for this sensor."""
        if self.coordinator.data is None:
            return None
        # coordinator.data is now a list of units
        return next(
            (
                u
                for u in self.coordinator.data
                if isinstance(u, dict) and u.get("unit_id") == self.unit_id
            ),
            None,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""

        # Find the unit data for this sensor
        unit_data = self.get_unit_data()
        if self.entity_description.key == "status":
            if unit_data is None:
                return "offline"
            return "online"

        if unit_data is None:
            return None

        if self.entity_description.key == "temperature":
            climate_data = unit_data.get("climate", {})
            if temp := climate_data.get("RoomTemp"):
                try:
                    return float(temp)
                except (ValueError, TypeError):
                    _LOGGER.error("Failed to convert temperature to float: %s", temp)
            return None

        if self.entity_description.key == "humidity":
            climate_data = unit_data.get("climate", {})
            if humidity := climate_data.get("RoomHumidity"):
                try:
                    return float(humidity)
                except (ValueError, TypeError):
                    _LOGGER.error("Failed to convert humidity to float: %s", humidity)
            return None
        return None
