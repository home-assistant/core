"""Platform for Mazda sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
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
class MazdaSensorRequiredKeysMixin:
    """Mixin for required keys."""

    # Function to determine the value for this sensor, given the coordinator data and the configured unit system
    value: Callable[[dict[str, Any], UnitSystem], StateType]


@dataclass
class MazdaSensorEntityDescription(
    SensorEntityDescription, MazdaSensorRequiredKeysMixin
):
    """Describes a Mazda sensor entity."""

    # Function to determine whether the vehicle supports this sensor, given the coordinator data
    is_supported: Callable[[dict[str, Any]], bool] = lambda data: True

    # Function to determine the unit of measurement for this sensor, given the configured unit system
    # Falls back to description.native_unit_of_measurement if it is not provided
    unit: Callable[[UnitSystem], str | None] | None = None


def _get_distance_unit(unit_system):
    """Return the distance unit for the given unit system."""
    if unit_system.name == CONF_UNIT_SYSTEM_IMPERIAL:
        return LENGTH_MILES
    return LENGTH_KILOMETERS


def _fuel_remaining_percentage_supported(data):
    """Determine if fuel remaining percentage is supported."""
    return (not data["isElectric"]) and (
        data["status"]["fuelRemainingPercent"] is not None
    )


def _fuel_distance_remaining_supported(data):
    """Determine if fuel distance remaining is supported."""
    return (not data["isElectric"]) and (
        data["status"]["fuelDistanceRemainingKm"] is not None
    )


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


def _ev_charge_level_supported(data):
    """Determine if charge level is supported."""
    return (
        data["isElectric"]
        and data["evStatus"]["chargeInfo"]["batteryLevelPercentage"] is not None
    )


def _ev_remaining_range_supported(data):
    """Determine if remaining range is supported."""
    return (
        data["isElectric"]
        and data["evStatus"]["chargeInfo"]["drivingRangeKm"] is not None
    )


def _fuel_distance_remaining_value(data, unit_system):
    """Get the fuel distance remaining value."""
    return round(
        unit_system.length(data["status"]["fuelDistanceRemainingKm"], LENGTH_KILOMETERS)
    )


def _odometer_value(data, unit_system):
    """Get the odometer value."""
    # In order to match the behavior of the Mazda mobile app, we always round down
    return int(unit_system.length(data["status"]["odometerKm"], LENGTH_KILOMETERS))


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


def _ev_charge_level_value(data, unit_system):
    """Get the charge level value."""
    return round(data["evStatus"]["chargeInfo"]["batteryLevelPercentage"])


def _ev_remaining_range_value(data, unit_system):
    """Get the remaining range value."""
    return round(
        unit_system.length(
            data["evStatus"]["chargeInfo"]["drivingRangeKm"], LENGTH_KILOMETERS
        )
    )


SENSOR_ENTITIES = [
    MazdaSensorEntityDescription(
        key="fuel_remaining_percentage",
        name="Fuel remaining percentage",
        icon="mdi:gas-station",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        is_supported=_fuel_remaining_percentage_supported,
        value=lambda data, unit_system: data["status"]["fuelRemainingPercent"],
    ),
    MazdaSensorEntityDescription(
        key="fuel_distance_remaining",
        name="Fuel distance remaining",
        icon="mdi:gas-station",
        unit=_get_distance_unit,
        state_class=SensorStateClass.MEASUREMENT,
        is_supported=_fuel_distance_remaining_supported,
        value=_fuel_distance_remaining_value,
    ),
    MazdaSensorEntityDescription(
        key="odometer",
        name="Odometer",
        icon="mdi:speedometer",
        unit=_get_distance_unit,
        state_class=SensorStateClass.TOTAL_INCREASING,
        is_supported=lambda data: data["status"]["odometerKm"] is not None,
        value=_odometer_value,
    ),
    MazdaSensorEntityDescription(
        key="front_left_tire_pressure",
        name="Front left tire pressure",
        icon="mdi:car-tire-alert",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_PSI,
        state_class=SensorStateClass.MEASUREMENT,
        is_supported=_front_left_tire_pressure_supported,
        value=_front_left_tire_pressure_value,
    ),
    MazdaSensorEntityDescription(
        key="front_right_tire_pressure",
        name="Front right tire pressure",
        icon="mdi:car-tire-alert",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_PSI,
        state_class=SensorStateClass.MEASUREMENT,
        is_supported=_front_right_tire_pressure_supported,
        value=_front_right_tire_pressure_value,
    ),
    MazdaSensorEntityDescription(
        key="rear_left_tire_pressure",
        name="Rear left tire pressure",
        icon="mdi:car-tire-alert",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_PSI,
        state_class=SensorStateClass.MEASUREMENT,
        is_supported=_rear_left_tire_pressure_supported,
        value=_rear_left_tire_pressure_value,
    ),
    MazdaSensorEntityDescription(
        key="rear_right_tire_pressure",
        name="Rear right tire pressure",
        icon="mdi:car-tire-alert",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_PSI,
        state_class=SensorStateClass.MEASUREMENT,
        is_supported=_rear_right_tire_pressure_supported,
        value=_rear_right_tire_pressure_value,
    ),
    MazdaSensorEntityDescription(
        key="ev_charge_level",
        name="Charge level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        is_supported=_ev_charge_level_supported,
        value=_ev_charge_level_value,
    ),
    MazdaSensorEntityDescription(
        key="ev_remaining_range",
        name="Remaining range",
        icon="mdi:ev-station",
        unit=_get_distance_unit,
        state_class=SensorStateClass.MEASUREMENT,
        is_supported=_ev_remaining_range_supported,
        value=_ev_remaining_range_value,
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

        self._attr_unique_id = f"{self.vin}_{description.key}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement for the sensor, according to the configured unit system."""
        if unit_fn := self.entity_description.unit:
            return unit_fn(self.hass.config.units)
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.entity_description.value(self.data, self.hass.config.units)
