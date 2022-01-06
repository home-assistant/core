"""Platform for Mazda sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_UNIT_SYSTEM_IMPERIAL,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    PERCENTAGE,
    PRESSURE_PSI,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_system import UnitSystem

from . import MazdaEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN


@dataclass
class MazdaSensorEntityDescription(SensorEntityDescription):
    """Describes a Mazda sensor entity."""

    # Suffix to be appended to the vehicle name to obtain the sensor name
    name_suffix: str | None = None

    # Function to determine whether the vehicle supports this sensor, given the coordinator data
    is_supported: Callable[[dict], bool] = lambda data: True

    # Function to determine the unit of measurement for this sensor, given the configured unit system
    unit: Callable[[UnitSystem], str | None] = lambda unit_system: None

    # Function to determine the value for this sensor, given the coordinator data and the configured unit system
    value: Callable[
        [dict, UnitSystem], StateType | None
    ] = lambda data, unit_system: None


def _get_distance_unit(unit_system):
    """Return the distance unit for the given unit system."""
    if unit_system.name == CONF_UNIT_SYSTEM_IMPERIAL:
        return LENGTH_MILES
    return LENGTH_KILOMETERS


def _front_left_tire_pressure_supported(data):
    """Determine if front left tire pressure is supported."""
    return data["status"]["tirePressure"]["frontLeftTirePressurePsi"] is not None


def _front_right_tire_pressure_supported(data):
    """Determine if front right tire pressure is supported."""
    return data["status"]["tirePressure"]["frontRightTirePressurePsi"] is not None


def _rear_left_tire_pressure_supported(data):
    """Determine if rear left tire pressure is supported."""
    return data["status"]["tirePressure"]["rearLeftTirePressurePsi"] is not None


def _rear_right_tire_pressure_supported(data):
    """Determine if rear right tire pressure is supported."""
    return data["status"]["tirePressure"]["rearRightTirePressurePsi"] is not None


def _fuel_distance_remaining_value(data, unit_system):
    """Get the fuel distance remaining value."""
    return round(
        unit_system.length(data["status"]["fuelDistanceRemainingKm"], LENGTH_KILOMETERS)
    )


def _odometer_value(data, unit_system):
    """Get the odometer value."""
    return round(unit_system.length(data["status"]["odometerKm"], LENGTH_KILOMETERS))


def _front_left_tire_pressure_value(data, unit_system):
    """Get the front left tire pressure value."""
    return round(data["status"]["tirePressure"]["frontLeftTirePressurePsi"])


def _front_right_tire_pressure_value(data, unit_system):
    """Get the front right tire pressure value."""
    return round(data["status"]["tirePressure"]["frontRightTirePressurePsi"])


def _rear_left_tire_pressure_value(data, unit_system):
    """Get the rear left tire pressure value."""
    return round(data["status"]["tirePressure"]["rearLeftTirePressurePsi"])


def _rear_right_tire_pressure_value(data, unit_system):
    """Get the rear right tire pressure value."""
    return round(data["status"]["tirePressure"]["rearRightTirePressurePsi"])


SENSOR_ENTITIES = [
    MazdaSensorEntityDescription(
        key="fuel_remaining_percentage",
        name_suffix="Fuel Remaining Percentage",
        icon="mdi:gas-station",
        unit=lambda unit_system: PERCENTAGE,
        is_supported=lambda data: data["status"]["fuelRemainingPercent"] is not None,
        value=lambda data, unit_system: data["status"]["fuelRemainingPercent"],
    ),
    MazdaSensorEntityDescription(
        key="fuel_distance_remaining",
        name_suffix="Fuel Distance Remaining",
        icon="mdi:gas-station",
        unit=_get_distance_unit,
        is_supported=lambda data: data["status"]["fuelDistanceRemainingKm"] is not None,
        value=_fuel_distance_remaining_value,
    ),
    MazdaSensorEntityDescription(
        key="odometer",
        name_suffix="Odometer",
        icon="mdi:speedometer",
        unit=_get_distance_unit,
        is_supported=lambda data: data["status"]["odometerKm"] is not None,
        value=_odometer_value,
    ),
    MazdaSensorEntityDescription(
        key="front_left_tire_pressure",
        name_suffix="Front Left Tire Pressure",
        icon="mdi:car-tire-alert",
        unit=lambda unit_system: PRESSURE_PSI,
        is_supported=_front_left_tire_pressure_supported,
        value=_front_left_tire_pressure_value,
    ),
    MazdaSensorEntityDescription(
        key="front_right_tire_pressure",
        name_suffix="Front Right Tire Pressure",
        icon="mdi:car-tire-alert",
        unit=lambda unit_system: PRESSURE_PSI,
        is_supported=_front_right_tire_pressure_supported,
        value=_front_right_tire_pressure_value,
    ),
    MazdaSensorEntityDescription(
        key="rear_left_tire_pressure",
        name_suffix="Rear Left Tire Pressure",
        icon="mdi:car-tire-alert",
        unit=lambda unit_system: PRESSURE_PSI,
        is_supported=_rear_left_tire_pressure_supported,
        value=_rear_left_tire_pressure_value,
    ),
    MazdaSensorEntityDescription(
        key="rear_right_tire_pressure",
        name_suffix="Rear Right Tire Pressure",
        icon="mdi:car-tire-alert",
        unit=lambda unit_system: PRESSURE_PSI,
        is_supported=_rear_right_tire_pressure_supported,
        value=_rear_right_tire_pressure_value,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    entities: list[SensorEntity] = []

    for index, data in enumerate(coordinator.data):
        for description in SENSOR_ENTITIES:
            if description.is_supported(data):
                entities.append(
                    MazdaSensorEntity(client, coordinator, index, description)
                )

    async_add_entities(entities)


class MazdaSensorEntity(MazdaEntity, SensorEntity):
    """Representation of a Mazda vehicle sensor."""

    entity_description: MazdaSensorEntityDescription

    def __init__(self, client, coordinator, index, description):
        """Initialize Mazda sensor."""
        super().__init__(client, coordinator, index)
        self.entity_description = description

        self._attr_name = f"{self.vehicle_name} {description.name_suffix}"
        self._attr_unique_id = f"{self.vin}_{description.key}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement for the sensor, according to the configured unit system."""
        return self.entity_description.unit(self.hass.config.units)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.entity_description.value(self.data, self.hass.config.units)
