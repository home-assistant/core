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
        api_variable_key="_today_energy",
        api_variable_unit="_today_energy_metric",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    SunWEGSensorEntityDescription(
        key="inverter_energy_total",
        name="Lifetime energy output",
        api_variable_key="_total_energy",
        api_variable_unit="_total_energy_metric",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL,
        never_resets=True,
    ),
    SunWEGSensorEntityDescription(
        key="inverter_frequency",
        name="AC frequency",
        api_variable_key="_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        suggested_display_precision=1,
    ),
    SunWEGSensorEntityDescription(
        key="inverter_current_wattage",
        name="Output power",
        api_variable_key="_power",
        api_variable_unit="_power_metric",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SunWEGSensorEntityDescription(
        key="inverter_temperature",
        name="Temperature",
        api_variable_key="_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:temperature-celsius",
        suggested_display_precision=1,
    ),
    SunWEGSensorEntityDescription(
        key="inverter_power_factor",
        name="Power Factor",
        api_variable_key="_power_factor",
        suggested_display_precision=1,
    ),
)
