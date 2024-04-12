"""SunWEG Sensor definitions for Totals."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy, UnitOfPower

from .sensor_entity_description import SunWEGSensorEntityDescription

TOTAL_SENSOR_TYPES: tuple[SunWEGSensorEntityDescription, ...] = (
    SunWEGSensorEntityDescription(
        key="total_money_total",
        name="Money lifetime",
        api_variable_key="saving",
        icon="mdi:cash",
        native_unit_of_measurement="R$",
        suggested_display_precision=2,
    ),
    SunWEGSensorEntityDescription(
        key="total_energy_today",
        name="Energy Today",
        api_variable_key="today_energy",
        api_variable_unit="today_energy_metric",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SunWEGSensorEntityDescription(
        key="total_output_power",
        name="Output Power",
        api_variable_key="total_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SunWEGSensorEntityDescription(
        key="total_energy_output",
        name="Lifetime energy output",
        api_variable_key="total_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        never_resets=True,
    ),
    SunWEGSensorEntityDescription(
        key="kwh_per_kwp",
        name="kWh per kWp",
        api_variable_key="kwh_per_kwp",
    ),
    SunWEGSensorEntityDescription(
        key="last_update",
        name="Last Update",
        api_variable_key="last_update",
        device_class=SensorDeviceClass.DATE,
    ),
)
