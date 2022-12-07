"""Growatt Sensor definitions for the Mix type."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_KILO_WATT,
    POWER_WATT,
)

from .sensor_entity_description import GrowattSensorEntityDescription

MIX_SENSOR_TYPES: tuple[GrowattSensorEntityDescription, ...] = (
    # Values from 'mix_info' API call
    GrowattSensorEntityDescription(
        key="mix_statement_of_charge",
        name="Statement of charge",
        api_key="capacity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
    ),
    GrowattSensorEntityDescription(
        key="mix_battery_charge_today",
        name="Battery charged today",
        api_key="eBatChargeToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_battery_charge_lifetime",
        name="Lifetime battery charged",
        api_key="eBatChargeTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="mix_battery_discharge_today",
        name="Battery discharged today",
        api_key="eBatDisChargeToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_battery_discharge_lifetime",
        name="Lifetime battery discharged",
        api_key="eBatDisChargeTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="mix_solar_generation_today",
        name="Solar energy today",
        api_key="epvToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_solar_generation_lifetime",
        name="Lifetime solar energy",
        api_key="epvTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="mix_battery_discharge_w",
        name="Battery discharging W",
        api_key="pDischarge1",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_battery_voltage",
        name="Battery voltage",
        api_key="vbat",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    GrowattSensorEntityDescription(
        key="mix_pv1_voltage",
        name="PV1 voltage",
        api_key="vpv1",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    GrowattSensorEntityDescription(
        key="mix_pv2_voltage",
        name="PV2 voltage",
        api_key="vpv2",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    # Values from 'mix_totals' API call
    GrowattSensorEntityDescription(
        key="mix_load_consumption_today",
        name="Load consumption today",
        api_key="elocalLoadToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_load_consumption_lifetime",
        name="Lifetime load consumption",
        api_key="elocalLoadTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="mix_export_to_grid_today",
        name="Export to grid today",
        api_key="etoGridToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_export_to_grid_lifetime",
        name="Lifetime export to grid",
        api_key="etogridTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    # Values from 'mix_system_status' API call
    GrowattSensorEntityDescription(
        key="mix_battery_charge",
        name="Battery charging",
        api_key="chargePower",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_load_consumption",
        name="Load consumption",
        api_key="pLocalLoad",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_wattage_pv_1",
        name="PV1 Wattage",
        api_key="pPv1",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_wattage_pv_2",
        name="PV2 Wattage",
        api_key="pPv2",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_wattage_pv_all",
        name="All PV Wattage",
        api_key="ppv",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_export_to_grid",
        name="Export to grid",
        api_key="pactogrid",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_import_from_grid",
        name="Import from grid",
        api_key="pactouser",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_battery_discharge_kw",
        name="Battery discharging kW",
        api_key="pdisCharge1",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_grid_voltage",
        name="Grid voltage",
        api_key="vAc1",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    # Values from 'mix_detail' API call
    GrowattSensorEntityDescription(
        key="mix_system_production_today",
        name="System production today (self-consumption + export)",
        api_key="eCharge",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_load_consumption_solar_today",
        name="Load consumption today (solar)",
        api_key="eChargeToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_self_consumption_today",
        name="Self consumption today (solar + battery)",
        api_key="eChargeToday1",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_load_consumption_battery_today",
        name="Load consumption today (battery)",
        api_key="echarge1",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_import_from_grid_today",
        name="Import from grid today (load)",
        api_key="etouser",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    # This sensor is manually created using the most recent X-Axis value from the chartData
    GrowattSensorEntityDescription(
        key="mix_last_update",
        name="Last Data Update",
        api_key="lastdataupdate",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    # Values from 'dashboard_data' API call
    GrowattSensorEntityDescription(
        key="mix_import_from_grid_today_combined",
        name="Import from grid today (load + charging)",
        api_key="etouser_combined",  # This id is not present in the raw API data, it is added by the sensor
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        previous_value_drop_threshold=0.2,
    ),
)
