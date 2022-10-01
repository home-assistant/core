"""Support for Subaru sensors."""
from __future__ import annotations

import logging
from typing import Any

import subarulink.const as sc

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ELECTRIC_POTENTIAL_VOLT,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    PERCENTAGE,
    PRESSURE_HPA,
    TEMP_CELSIUS,
    VOLUME_GALLONS,
    VOLUME_LITERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util.unit_conversion import DistanceConverter, VolumeConverter
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, LENGTH_UNITS, PRESSURE_UNITS

from . import get_device_info
from .const import (
    API_GEN_2,
    DOMAIN,
    ENTRY_COORDINATOR,
    ENTRY_VEHICLES,
    VEHICLE_API_GEN,
    VEHICLE_HAS_EV,
    VEHICLE_HAS_SAFETY_SERVICE,
    VEHICLE_STATUS,
    VEHICLE_VIN,
)

_LOGGER = logging.getLogger(__name__)

# Fuel consumption units
FUEL_CONSUMPTION_LITERS_PER_HUNDRED_KILOMETERS = "L/100km"
FUEL_CONSUMPTION_MILES_PER_GALLON = "mi/gal"

L_PER_GAL = VolumeConverter.convert(1, VOLUME_GALLONS, VOLUME_LITERS)
KM_PER_MI = DistanceConverter.convert(1, LENGTH_MILES, LENGTH_KILOMETERS)

# Sensor available to "Subaru Safety Plus" subscribers with Gen1 or Gen2 vehicles
SAFETY_SENSORS = [
    SensorEntityDescription(
        key=sc.ODOMETER,
        icon="mdi:road-variant",
        name="Odometer",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
]

# Sensors available to "Subaru Safety Plus" subscribers with Gen2 vehicles
API_GEN_2_SENSORS = [
    SensorEntityDescription(
        key=sc.AVG_FUEL_CONSUMPTION,
        icon="mdi:leaf",
        name="Avg Fuel Consumption",
        native_unit_of_measurement=FUEL_CONSUMPTION_LITERS_PER_HUNDRED_KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.DIST_TO_EMPTY,
        icon="mdi:gas-station",
        name="Range",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.TIRE_PRESSURE_FL,
        device_class=SensorDeviceClass.PRESSURE,
        name="Tire Pressure FL",
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.TIRE_PRESSURE_FR,
        device_class=SensorDeviceClass.PRESSURE,
        name="Tire Pressure FR",
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.TIRE_PRESSURE_RL,
        device_class=SensorDeviceClass.PRESSURE,
        name="Tire Pressure RL",
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.TIRE_PRESSURE_RR,
        device_class=SensorDeviceClass.PRESSURE,
        name="Tire Pressure RR",
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.EXTERNAL_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        name="External Temp",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.BATTERY_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        name="12V Battery Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

# Sensors available to "Subaru Safety Plus" subscribers with PHEV vehicles
EV_SENSORS = [
    SensorEntityDescription(
        key=sc.EV_DISTANCE_TO_EMPTY,
        icon="mdi:ev-station",
        name="EV Range",
        native_unit_of_measurement=LENGTH_MILES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.EV_STATE_OF_CHARGE_PERCENT,
        device_class=SensorDeviceClass.BATTERY,
        name="EV Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.EV_TIME_TO_FULLY_CHARGED_UTC,
        device_class=SensorDeviceClass.TIMESTAMP,
        name="EV Time to Full Charge",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Subaru sensors by config_entry."""
    entry = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = entry[ENTRY_COORDINATOR]
    vehicle_info = entry[ENTRY_VEHICLES]
    entities = []
    for info in vehicle_info.values():
        entities.extend(create_vehicle_sensors(info, coordinator))
    async_add_entities(entities)


def create_vehicle_sensors(
    vehicle_info, coordinator: DataUpdateCoordinator
) -> list[SubaruSensor]:
    """Instantiate all available sensors for the vehicle."""
    sensor_descriptions_to_add = []
    if vehicle_info[VEHICLE_HAS_SAFETY_SERVICE]:
        sensor_descriptions_to_add.extend(SAFETY_SENSORS)

        if vehicle_info[VEHICLE_API_GEN] == API_GEN_2:
            sensor_descriptions_to_add.extend(API_GEN_2_SENSORS)

        if vehicle_info[VEHICLE_HAS_EV]:
            sensor_descriptions_to_add.extend(EV_SENSORS)

    return [
        SubaruSensor(
            vehicle_info,
            coordinator,
            description,
        )
        for description in sensor_descriptions_to_add
    ]


class SubaruSensor(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]], SensorEntity
):
    """Class for Subaru sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        vehicle_info: dict,
        coordinator: DataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.vin = vehicle_info[VEHICLE_VIN]
        self.entity_description = description
        self._attr_device_info = get_device_info(vehicle_info)
        self._attr_unique_id = f"{self.vin}_{description.name}"

    @property
    def native_value(self) -> None | int | float:
        """Return the state of the sensor."""
        vehicle_data = self.coordinator.data[self.vin]
        current_value = vehicle_data[VEHICLE_STATUS].get(self.entity_description.key)
        unit = self.entity_description.native_unit_of_measurement
        unit_system = self.hass.config.units

        if current_value is None:
            return None

        if unit in LENGTH_UNITS:
            return round(unit_system.length(current_value, unit), 1)

        if unit in PRESSURE_UNITS and unit_system == IMPERIAL_SYSTEM:
            return round(
                unit_system.pressure(current_value, unit),
                1,
            )

        if (
            unit
            in [
                FUEL_CONSUMPTION_LITERS_PER_HUNDRED_KILOMETERS,
                FUEL_CONSUMPTION_MILES_PER_GALLON,
            ]
            and unit_system == IMPERIAL_SYSTEM
        ):
            return round((100.0 * L_PER_GAL) / (KM_PER_MI * current_value), 1)

        return current_value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit_of_measurement of the device."""
        unit = self.entity_description.native_unit_of_measurement

        if unit in LENGTH_UNITS:
            return self.hass.config.units.length_unit

        if unit in PRESSURE_UNITS:
            if self.hass.config.units == IMPERIAL_SYSTEM:
                return self.hass.config.units.pressure_unit

        if unit in [
            FUEL_CONSUMPTION_LITERS_PER_HUNDRED_KILOMETERS,
            FUEL_CONSUMPTION_MILES_PER_GALLON,
        ]:
            if self.hass.config.units == IMPERIAL_SYSTEM:
                return FUEL_CONSUMPTION_MILES_PER_GALLON

        return unit

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        last_update_success = super().available
        if last_update_success and self.vin not in self.coordinator.data:
            return False
        return last_update_success
