"""Read status of growatt inverters."""
from __future__ import annotations

from dataclasses import dataclass
import datetime
import json
import logging

import growattServer

from homeassistant.components.sensor import (
    STATE_CLASS_TOTAL,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_KILO_WATT,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.util import Throttle, dt

from .const import CONF_PLANT_ID, DEFAULT_PLANT_ID, DEFAULT_URL

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=1)


@dataclass
class GrowattRequiredKeysMixin:
    """Mixin for required keys."""

    api_key: str


@dataclass
class GrowattSensorEntityDescription(SensorEntityDescription, GrowattRequiredKeysMixin):
    """Describes Growatt sensor entity."""

    precision: int | None = None
    currency: bool = False


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
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="total_output_power",
        name="Output Power",
        api_key="invTodayPpv",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    GrowattSensorEntityDescription(
        key="total_energy_output",
        name="Lifetime energy output",
        api_key="totalEnergy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="total_maximum_output",
        name="Maximum power",
        api_key="nominalPower",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
)

INVERTER_SENSOR_TYPES: tuple[GrowattSensorEntityDescription, ...] = (
    GrowattSensorEntityDescription(
        key="inverter_energy_today",
        name="Energy today",
        api_key="powerToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_energy_total",
        name="Lifetime energy output",
        api_key="powerTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        precision=1,
        state_class=STATE_CLASS_TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="inverter_voltage_input_1",
        name="Input 1 voltage",
        api_key="vpv1",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        precision=2,
    ),
    GrowattSensorEntityDescription(
        key="inverter_amperage_input_1",
        name="Input 1 Amperage",
        api_key="ipv1",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_wattage_input_1",
        name="Input 1 Wattage",
        api_key="ppv1",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_voltage_input_2",
        name="Input 2 voltage",
        api_key="vpv2",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_amperage_input_2",
        name="Input 2 Amperage",
        api_key="ipv2",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_wattage_input_2",
        name="Input 2 Wattage",
        api_key="ppv2",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_voltage_input_3",
        name="Input 3 voltage",
        api_key="vpv3",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_amperage_input_3",
        name="Input 3 Amperage",
        api_key="ipv3",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_wattage_input_3",
        name="Input 3 Wattage",
        api_key="ppv3",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_internal_wattage",
        name="Internal wattage",
        api_key="ppv",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_reactive_voltage",
        name="Reactive voltage",
        api_key="vacr",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_inverter_reactive_amperage",
        name="Reactive amperage",
        api_key="iacr",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_frequency",
        name="AC frequency",
        api_key="fac",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_current_wattage",
        name="Output power",
        api_key="pac",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_current_reactive_wattage",
        name="Reactive wattage",
        api_key="pacr",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_ipm_temperature",
        name="Intelligent Power Management temperature",
        api_key="ipmTemperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="inverter_temperature",
        name="Temperature",
        api_key="temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        precision=1,
    ),
)

TLX_SENSOR_TYPES: tuple[GrowattSensorEntityDescription, ...] = (
    GrowattSensorEntityDescription(
        key="tlx_energy_today",
        name="Energy today",
        api_key="eacToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_energy_total",
        name="Lifetime energy output",
        api_key="eacTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_energy_total_input_1",
        name="Lifetime total energy input 1",
        api_key="epv1Total",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_energy_today_input_1",
        name="Energy Today Input 1",
        api_key="epv1Today",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_voltage_input_1",
        name="Input 1 voltage",
        api_key="vpv1",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_amperage_input_1",
        name="Input 1 Amperage",
        api_key="ipv1",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_wattage_input_1",
        name="Input 1 Wattage",
        api_key="ppv1",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_energy_total_input_2",
        name="Lifetime total energy input 2",
        api_key="epv2Total",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_energy_today_input_2",
        name="Energy Today Input 2",
        api_key="epv2Today",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_voltage_input_2",
        name="Input 2 voltage",
        api_key="vpv2",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_amperage_input_2",
        name="Input 2 Amperage",
        api_key="ipv2",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_wattage_input_2",
        name="Input 2 Wattage",
        api_key="ppv2",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_internal_wattage",
        name="Internal wattage",
        api_key="ppv",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_reactive_voltage",
        name="Reactive voltage",
        api_key="vacrs",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_frequency",
        name="AC frequency",
        api_key="fac",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_current_wattage",
        name="Output power",
        api_key="pac",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_temperature_1",
        name="Temperature 1",
        api_key="temp1",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_temperature_2",
        name="Temperature 2",
        api_key="temp2",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_temperature_3",
        name="Temperature 3",
        api_key="temp3",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_temperature_4",
        name="Temperature 4",
        api_key="temp4",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        precision=1,
    ),
    GrowattSensorEntityDescription(
        key="tlx_temperature_5",
        name="Temperature 5",
        api_key="temp5",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        precision=1,
    ),
)

STORAGE_SENSOR_TYPES: tuple[GrowattSensorEntityDescription, ...] = (
    GrowattSensorEntityDescription(
        key="storage_storage_production_today",
        name="Storage production today",
        api_key="eBatDisChargeToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="storage_storage_production_lifetime",
        name="Lifetime Storage production",
        api_key="eBatDisChargeTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="storage_grid_discharge_today",
        name="Grid discharged today",
        api_key="eacDisChargeToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="storage_load_consumption_today",
        name="Load consumption today",
        api_key="eopDischrToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="storage_load_consumption_lifetime",
        name="Lifetime load consumption",
        api_key="eopDischrTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="storage_grid_charged_today",
        name="Grid charged today",
        api_key="eacChargeToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="storage_charge_storage_lifetime",
        name="Lifetime storaged charged",
        api_key="eChargeTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="storage_solar_production",
        name="Solar power production",
        api_key="ppv",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    GrowattSensorEntityDescription(
        key="storage_battery_percentage",
        name="Battery percentage",
        api_key="capacity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
    ),
    GrowattSensorEntityDescription(
        key="storage_power_flow",
        name="Storage charging/ discharging(-ve)",
        api_key="pCharge",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    GrowattSensorEntityDescription(
        key="storage_load_consumption_solar_storage",
        name="Load consumption(Solar + Storage)",
        api_key="rateVA",
        native_unit_of_measurement="VA",
    ),
    GrowattSensorEntityDescription(
        key="storage_charge_today",
        name="Charge today",
        api_key="eChargeToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="storage_import_from_grid",
        name="Import from grid",
        api_key="pAcInPut",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    GrowattSensorEntityDescription(
        key="storage_import_from_grid_today",
        name="Import from grid today",
        api_key="eToUserToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="storage_import_from_grid_total",
        name="Import from grid total",
        api_key="eToUserTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="storage_load_consumption",
        name="Load consumption",
        api_key="outPutPower",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    GrowattSensorEntityDescription(
        key="storage_grid_voltage",
        name="AC input voltage",
        api_key="vGrid",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        precision=2,
    ),
    GrowattSensorEntityDescription(
        key="storage_pv_charging_voltage",
        name="PV charging voltage",
        api_key="vpv",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        precision=2,
    ),
    GrowattSensorEntityDescription(
        key="storage_ac_input_frequency_out",
        name="AC input frequency",
        api_key="freqOutPut",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        precision=2,
    ),
    GrowattSensorEntityDescription(
        key="storage_output_voltage",
        name="Output voltage",
        api_key="outPutVolt",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        precision=2,
    ),
    GrowattSensorEntityDescription(
        key="storage_ac_output_frequency",
        name="Ac output frequency",
        api_key="freqGrid",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        precision=2,
    ),
    GrowattSensorEntityDescription(
        key="storage_current_PV",
        name="Solar charge current",
        api_key="iAcCharge",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        precision=2,
    ),
    GrowattSensorEntityDescription(
        key="storage_current_1",
        name="Solar current to storage",
        api_key="iChargePV1",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        precision=2,
    ),
    GrowattSensorEntityDescription(
        key="storage_grid_amperage_input",
        name="Grid charge current",
        api_key="chgCurr",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        precision=2,
    ),
    GrowattSensorEntityDescription(
        key="storage_grid_out_current",
        name="Grid out current",
        api_key="outPutCurrent",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        precision=2,
    ),
    GrowattSensorEntityDescription(
        key="storage_battery_voltage",
        name="Battery voltage",
        api_key="vBat",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        precision=2,
    ),
    GrowattSensorEntityDescription(
        key="storage_load_percentage",
        name="Load percentage",
        api_key="loadPercent",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
        precision=2,
    ),
)

MIX_SENSOR_TYPES: tuple[GrowattSensorEntityDescription, ...] = (
    # Values from 'mix_info' API call
    GrowattSensorEntityDescription(
        key="mix_statement_of_charge",
        name="Statement of charge",
        api_key="capacity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
    ),
    GrowattSensorEntityDescription(
        key="mix_battery_charge_today",
        name="Battery charged today",
        api_key="eBatChargeToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_battery_charge_lifetime",
        name="Lifetime battery charged",
        api_key="eBatChargeTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="mix_battery_discharge_today",
        name="Battery discharged today",
        api_key="eBatDisChargeToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_battery_discharge_lifetime",
        name="Lifetime battery discharged",
        api_key="eBatDisChargeTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="mix_solar_generation_today",
        name="Solar energy today",
        api_key="epvToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_solar_generation_lifetime",
        name="Lifetime solar energy",
        api_key="epvTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="mix_battery_discharge_w",
        name="Battery discharging W",
        api_key="pDischarge1",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_battery_voltage",
        name="Battery voltage",
        api_key="vbat",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
    ),
    GrowattSensorEntityDescription(
        key="mix_pv1_voltage",
        name="PV1 voltage",
        api_key="vpv1",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
    ),
    GrowattSensorEntityDescription(
        key="mix_pv2_voltage",
        name="PV2 voltage",
        api_key="vpv2",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
    ),
    # Values from 'mix_totals' API call
    GrowattSensorEntityDescription(
        key="mix_load_consumption_today",
        name="Load consumption today",
        api_key="elocalLoadToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_load_consumption_lifetime",
        name="Lifetime load consumption",
        api_key="elocalLoadTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
    ),
    GrowattSensorEntityDescription(
        key="mix_export_to_grid_today",
        name="Export to grid today",
        api_key="etoGridToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_export_to_grid_lifetime",
        name="Lifetime export to grid",
        api_key="etogridTotal",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
    ),
    # Values from 'mix_system_status' API call
    GrowattSensorEntityDescription(
        key="mix_battery_charge",
        name="Battery charging",
        api_key="chargePower",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_load_consumption",
        name="Load consumption",
        api_key="pLocalLoad",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_wattage_pv_1",
        name="PV1 Wattage",
        api_key="pPv1",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_wattage_pv_2",
        name="PV2 Wattage",
        api_key="pPv2",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_wattage_pv_all",
        name="All PV Wattage",
        api_key="ppv",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_export_to_grid",
        name="Export to grid",
        api_key="pactogrid",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_import_from_grid",
        name="Import from grid",
        api_key="pactouser",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_battery_discharge_kw",
        name="Battery discharging kW",
        api_key="pdisCharge1",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    GrowattSensorEntityDescription(
        key="mix_grid_voltage",
        name="Grid voltage",
        api_key="vAc1",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
    ),
    # Values from 'mix_detail' API call
    GrowattSensorEntityDescription(
        key="mix_system_production_today",
        name="System production today (self-consumption + export)",
        api_key="eCharge",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_load_consumption_solar_today",
        name="Load consumption today (solar)",
        api_key="eChargeToday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_self_consumption_today",
        name="Self consumption today (solar + battery)",
        api_key="eChargeToday1",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_load_consumption_battery_today",
        name="Load consumption today (battery)",
        api_key="echarge1",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    GrowattSensorEntityDescription(
        key="mix_import_from_grid_today",
        name="Import from grid today (load)",
        api_key="etouser",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    # This sensor is manually created using the most recent X-Axis value from the chartData
    GrowattSensorEntityDescription(
        key="mix_last_update",
        name="Last Data Update",
        api_key="lastdataupdate",
        native_unit_of_measurement=None,
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    # Values from 'dashboard_data' API call
    GrowattSensorEntityDescription(
        key="mix_import_from_grid_today_combined",
        name="Import from grid today (load + charging)",
        api_key="etouser_combined",  # This id is not present in the raw API data, it is added by the sensor
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
)


def get_device_list(api, config):
    """Retrieve the device list for the selected plant."""
    plant_id = config[CONF_PLANT_ID]

    # Log in to api and fetch first plant if no plant id is defined.
    login_response = api.login(config[CONF_USERNAME], config[CONF_PASSWORD])
    if not login_response["success"] and login_response["errCode"] == "102":
        _LOGGER.error("Username, Password or URL may be incorrect!")
        return
    user_id = login_response["user"]["id"]
    if plant_id == DEFAULT_PLANT_ID:
        plant_info = api.plant_list(user_id)
        plant_id = plant_info["data"][0]["plantId"]

    # Get a list of devices for specified plant to add sensors for.
    devices = api.device_list(plant_id)
    return [devices, plant_id]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Growatt sensor."""
    config = config_entry.data
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    url = config.get(CONF_URL, DEFAULT_URL)
    name = config[CONF_NAME]

    api = growattServer.GrowattApi()
    api.server_url = url

    devices, plant_id = await hass.async_add_executor_job(get_device_list, api, config)

    probe = GrowattData(api, username, password, plant_id, "total")
    entities = [
        GrowattInverter(
            probe,
            name=f"{name} Total",
            unique_id=f"{plant_id}-{description.key}",
            description=description,
        )
        for description in TOTAL_SENSOR_TYPES
    ]

    # Add sensors for each device in the specified plant.
    for device in devices:
        probe = GrowattData(
            api, username, password, device["deviceSn"], device["deviceType"]
        )
        sensor_descriptions = ()
        if device["deviceType"] == "inverter":
            sensor_descriptions = INVERTER_SENSOR_TYPES
        elif device["deviceType"] == "tlx":
            probe.plant_id = plant_id
            sensor_descriptions = TLX_SENSOR_TYPES
        elif device["deviceType"] == "storage":
            probe.plant_id = plant_id
            sensor_descriptions = STORAGE_SENSOR_TYPES
        elif device["deviceType"] == "mix":
            probe.plant_id = plant_id
            sensor_descriptions = MIX_SENSOR_TYPES
        else:
            _LOGGER.debug(
                "Device type %s was found but is not supported right now",
                device["deviceType"],
            )

        entities.extend(
            [
                GrowattInverter(
                    probe,
                    name=f"{device['deviceAilas']}",
                    unique_id=f"{device['deviceSn']}-{description.key}",
                    description=description,
                )
                for description in sensor_descriptions
            ]
        )

    async_add_entities(entities, True)


class GrowattInverter(SensorEntity):
    """Representation of a Growatt Sensor."""

    entity_description: GrowattSensorEntityDescription

    def __init__(
        self, probe, name, unique_id, description: GrowattSensorEntityDescription
    ):
        """Initialize a PVOutput sensor."""
        self.probe = probe
        self.entity_description = description

        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = unique_id
        self._attr_icon = "mdi:solar-power"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        result = self.probe.get_data(self.entity_description.api_key)
        if self.entity_description.precision is not None:
            result = round(result, self.entity_description.precision)
        return result

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        if self.entity_description.currency:
            return self.probe.get_data("currency")
        return super().native_unit_of_measurement

    def update(self):
        """Get the latest data from the Growat API and updates the state."""
        self.probe.update()


class GrowattData:
    """The class for handling data retrieval."""

    def __init__(self, api, username, password, device_id, growatt_type):
        """Initialize the probe."""

        self.growatt_type = growatt_type
        self.api = api
        self.device_id = device_id
        self.plant_id = None
        self.data = {}
        self.username = username
        self.password = password

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Update probe data."""
        self.api.login(self.username, self.password)
        _LOGGER.debug("Updating data for %s (%s)", self.device_id, self.growatt_type)
        try:
            if self.growatt_type == "total":
                total_info = self.api.plant_info(self.device_id)
                del total_info["deviceList"]
                # PlantMoneyText comes in as "3.1/€" split between value and currency
                plant_money_text, currency = total_info["plantMoneyText"].split("/")
                total_info["plantMoneyText"] = plant_money_text
                total_info["currency"] = currency
                self.data = total_info
            elif self.growatt_type == "inverter":
                inverter_info = self.api.inverter_detail(self.device_id)
                self.data = inverter_info
            elif self.growatt_type == "tlx":
                tlx_info = self.api.tlx_detail(self.device_id)
                self.data = tlx_info["data"]
            elif self.growatt_type == "storage":
                storage_info_detail = self.api.storage_params(self.device_id)[
                    "storageDetailBean"
                ]
                storage_energy_overview = self.api.storage_energy_overview(
                    self.plant_id, self.device_id
                )
                self.data = {**storage_info_detail, **storage_energy_overview}
            elif self.growatt_type == "mix":
                mix_info = self.api.mix_info(self.device_id)
                mix_totals = self.api.mix_totals(self.device_id, self.plant_id)
                mix_system_status = self.api.mix_system_status(
                    self.device_id, self.plant_id
                )

                mix_detail = self.api.mix_detail(self.device_id, self.plant_id)
                # Get the chart data and work out the time of the last entry, use this as the last time data was published to the Growatt Server
                mix_chart_entries = mix_detail["chartData"]
                sorted_keys = sorted(mix_chart_entries)

                # Create datetime from the latest entry
                date_now = dt.now().date()
                last_updated_time = dt.parse_time(str(sorted_keys[-1]))
                combined_timestamp = datetime.datetime.combine(
                    date_now, last_updated_time
                )
                # Convert datetime to UTC
                combined_timestamp_utc = dt.as_utc(combined_timestamp)
                mix_detail["lastdataupdate"] = combined_timestamp_utc.isoformat()

                # Dashboard data is largely inaccurate for mix system but it is the only call with the ability to return the combined
                # imported from grid value that is the combination of charging AND load consumption
                dashboard_data = self.api.dashboard_data(self.plant_id)
                # Dashboard values have units e.g. "kWh" as part of their returned string, so we remove it
                dashboard_values_for_mix = {
                    # etouser is already used by the results from 'mix_detail' so we rebrand it as 'etouser_combined'
                    "etouser_combined": float(
                        dashboard_data["etouser"].replace("kWh", "")
                    )
                }
                self.data = {
                    **mix_info,
                    **mix_totals,
                    **mix_system_status,
                    **mix_detail,
                    **dashboard_values_for_mix,
                }
        except json.decoder.JSONDecodeError:
            _LOGGER.error("Unable to fetch data from Growatt server")

    def get_data(self, variable):
        """Get the data."""
        return self.data.get(variable)
