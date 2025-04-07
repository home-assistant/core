"""Growatt Sensor definitions for the NOAH type."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)

from .sensor_entity_description import GrowattSensorEntityDescription

NOAH_SENSOR_TYPES: tuple[GrowattSensorEntityDescription, ...] = (
    GrowattSensorEntityDescription(
        key="noah_energy_today",
        translation_key="noah_energy_today",
        api_key="eacToday",  # <-- genaues Feld aus der Growatt-API
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    GrowattSensorEntityDescription(
        key="noah_energy_total",
        translation_key="noah_energy_total",
        api_key="eacTotal",  # <-- genaues Feld aus der Growatt-API
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    GrowattSensorEntityDescription(
        key="noah_battery_soc",
        translation_key="noah_battery_soc",
        api_key="soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GrowattSensorEntityDescription(
        key="noah_current_power",
        translation_key="noah_current_power",
        api_key="pac",  # bspw. 'pac' = aktuelle Leistung
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GrowattSensorEntityDescription(
        key="noah_charge_power",
        translation_key="noah_charge_power",
        api_key="chargePower",  # bspw. 'pac' = aktuelle Leistung
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GrowattSensorEntityDescription(
        key="noah_discharge_power",
        translation_key="noah_discharge_power",
        api_key="disChargePower",  # bspw. 'pac' = aktuelle Leistung
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GrowattSensorEntityDescription(
        key="noah_solar_power",
        translation_key="noah_solar_power",
        api_key="ppv",  # bspw. 'pac' = aktuelle Leistung
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    )
)
