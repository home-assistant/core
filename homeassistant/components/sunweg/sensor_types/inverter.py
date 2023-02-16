"""SunWEG Sensor definitions for the Inverter type."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)

from .sensor_entity_description import SunWEGSensorEntityDescription

INVERTER_SENSOR_TYPES: tuple[SunWEGSensorEntityDescription, ...] = (
    SunWEGSensorEntityDescription(
        key="inverter_energy_today",
        name="Energy today",
        api_key="today_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        precision=1,
    ),
    SunWEGSensorEntityDescription(
        key="inverter_energy_total",
        name="Lifetime energy output",
        api_key="total_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        precision=1,
        state_class=SensorStateClass.TOTAL,
    ),
    SunWEGSensorEntityDescription(
        key="inverter_frequency",
        name="AC frequency",
        api_key="frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        precision=1,
    ),
    SunWEGSensorEntityDescription(
        key="inverter_current_wattage",
        name="Output power",
        api_key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        precision=1,
    ),
    SunWEGSensorEntityDescription(
        key="inverter_temperature",
        name="Temperature",
        api_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:temperature-celsius",
        precision=1,
    ),
    SunWEGSensorEntityDescription(
        key="inverter_power_factor",
        name="Power Factor",
        api_key="power_factor",
        precision=1,
    ),
)
