"""Growatt Sensor definitions for Totals."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy, UnitOfPower

from .sensor_entity_description import GrowattSensorEntityDescription

TOTAL_SENSOR_TYPES: tuple[GrowattSensorEntityDescription, ...] = (
    GrowattSensorEntityDescription(
        key="total_money_today",
        translation_key="total_money_today",
        api_key="plantMoneyText",
        currency=True,
    ),
    GrowattSensorEntityDescription(
        key="total_money_total",
        translation_key="total_money_total",
        api_key="totalMoneyText",
        currency=True,
    ),
    GrowattSensorEntityDescription(
        key="total_energy_today",
        translation_key="total_energy_today",
        api_key="todayEnergy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="total_output_power",
        translation_key="total_output_power",
        api_key="invTodayPpv",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    GrowattSensorEntityDescription(
        key="total_energy_output",
        translation_key="total_energy_output",
        api_key="totalEnergy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="total_maximum_output",
        translation_key="total_maximum_output",
        api_key="nominalPower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
)
