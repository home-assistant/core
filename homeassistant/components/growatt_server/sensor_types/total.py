"""Growatt Sensor definitions for Totals."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import ENERGY_KILO_WATT_HOUR, POWER_WATT

from .sensor_entity_description import GrowattSensorEntityDescription

TOTAL_SENSOR_TYPES: tuple[GrowattSensorEntityDescription, ...] = (
    GrowattSensorEntityDescription(
        key="total_money_today",
        name="Total money today",
        api_key="plantMoneyText",
        currency=True,
    ),
    GrowattSensorEntityDescription(
        key="total_money_total",
        name="Money lifetime",
        api_key="totalMoneyText",
        currency=True,
    ),
    GrowattSensorEntityDescription(
        key="total_energy_today",
        name="Energy Today",
        api_key="todayEnergy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="total_output_power",
        name="Output Power",
        api_key="invTodayPpv",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    GrowattSensorEntityDescription(
        key="total_energy_output",
        name="Lifetime energy output",
        api_key="totalEnergy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="total_maximum_output",
        name="Maximum power",
        api_key="nominalPower",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
)
