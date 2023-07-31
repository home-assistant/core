"""Definitions for DSMR Reader sensors added to MQTT."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CURRENCY_EURO,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.util import dt as dt_util

PRICE_EUR_KWH: Final = f"EUR/{UnitOfEnergy.KILO_WATT_HOUR}"
PRICE_EUR_M3: Final = f"EUR/{UnitOfVolume.CUBIC_METERS}"


def dsmr_transform(value):
    """Transform DSMR version value to right format."""
    if value.isdigit():
        return float(value) / 10
    return value


def tariff_transform(value):
    """Transform tariff from number to description."""
    if value == "1":
        return "low"
    return "high"


@dataclass
class DSMRReaderSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description for DSMR Reader."""

    state: Callable | None = None


SENSORS: tuple[DSMRReaderSensorEntityDescription, ...] = (
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/electricity_delivered_1",
        translation_key="low_tariff_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/electricity_returned_1",
        translation_key="low_tariff_returned",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/electricity_delivered_2",
        translation_key="high_tariff_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/electricity_returned_2",
        translation_key="high_tariff_returned",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/electricity_currently_delivered",
        translation_key="current_power_usage",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/electricity_currently_returned",
        translation_key="current_power_return",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_currently_delivered_l1",
        translation_key="current_power_usage_l1",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_currently_delivered_l2",
        translation_key="current_power_usage_l2",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_currently_delivered_l3",
        translation_key="current_power_usage_l3",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_currently_returned_l1",
        translation_key="current_power_return_l1",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_currently_returned_l2",
        translation_key="current_power_return_l2",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_currently_returned_l3",
        translation_key="current_power_return_l3",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/extra_device_delivered",
        translation_key="gas_meter_usage",
        entity_registry_enabled_default=False,
        icon="mdi:fire",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_voltage_l1",
        translation_key="current_voltage_l1",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_voltage_l2",
        translation_key="current_voltage_l2",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_voltage_l3",
        translation_key="current_voltage_l3",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_power_current_l1",
        translation_key="phase_power_current_l1",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_power_current_l2",
        translation_key="phase_power_current_l2",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_power_current_l3",
        translation_key="phase_power_current_l3",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/timestamp",
        translation_key="telegram_timestamp",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        state=dt_util.parse_datetime,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/consumption/gas/delivered",
        translation_key="gas_usage",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/consumption/gas/currently_delivered",
        translation_key="current_gas_usage",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/consumption/gas/read_at",
        translation_key="gas_meter_read",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        state=dt_util.parse_datetime,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity1",
        translation_key="daily_low_tariff_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity2",
        translation_key="daily_high_tariff_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity1_returned",
        translation_key="daily_low_tariff_return",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity2_returned",
        translation_key="daily_high_tariff_return",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity_merged",
        translation_key="daily_power_usage_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity_returned_merged",
        translation_key="daily_power_return_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity1_cost",
        translation_key="daily_low_tariff_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity2_cost",
        translation_key="daily_high_tariff_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity_cost_merged",
        translation_key="daily_power_total_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/gas",
        translation_key="daily_gas_usage",
        icon="mdi:counter",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/gas_cost",
        translation_key="gas_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/total_cost",
        translation_key="total_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/energy_supplier_price_electricity_delivered_1",
        translation_key="low_tariff_delivered_price",
        icon="mdi:currency-eur",
        native_unit_of_measurement=PRICE_EUR_KWH,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/energy_supplier_price_electricity_delivered_2",
        translation_key="high_tariff_delivered_price",
        icon="mdi:currency-eur",
        native_unit_of_measurement=PRICE_EUR_KWH,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/energy_supplier_price_electricity_returned_1",
        translation_key="low_tariff_returned_price",
        icon="mdi:currency-eur",
        native_unit_of_measurement=PRICE_EUR_KWH,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/energy_supplier_price_electricity_returned_2",
        translation_key="high_tariff_returned_price",
        icon="mdi:currency-eur",
        native_unit_of_measurement=PRICE_EUR_KWH,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/energy_supplier_price_gas",
        translation_key="gas_price",
        icon="mdi:currency-eur",
        native_unit_of_measurement=PRICE_EUR_M3,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/fixed_cost",
        translation_key="current_day_fixed_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/dsmr_version",
        translation_key="dsmr_version",
        entity_registry_enabled_default=False,
        icon="mdi:alert-circle",
        state=dsmr_transform,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/electricity_tariff",
        translation_key="electricity_tariff",
        device_class=SensorDeviceClass.ENUM,
        options=["low", "high"],
        icon="mdi:flash",
        state=tariff_transform,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/power_failure_count",
        translation_key="power_failure_count",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/long_power_failure_count",
        translation_key="long_power_failure_count",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/voltage_sag_count_l1",
        translation_key="voltage_sag_l1",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/voltage_sag_count_l2",
        translation_key="voltage_sag_l2",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/voltage_sag_count_l3",
        translation_key="voltage_sag_l3",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/voltage_swell_count_l1",
        translation_key="voltage_swell_l1",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/voltage_swell_count_l2",
        translation_key="voltage_swell_l2",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/voltage_swell_count_l3",
        translation_key="voltage_swell_l3",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/rejected_telegrams",
        translation_key="rejected_telegrams",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity1",
        translation_key="current_month_low_tariff_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity2",
        translation_key="current_month_high_tariff_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity1_returned",
        translation_key="current_month_low_tariff_returned",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity2_returned",
        translation_key="current_month_high_tariff_returned",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity_merged",
        translation_key="current_month_power_usage_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity_returned_merged",
        translation_key="current_month_power_return_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity1_cost",
        translation_key="current_month_low_tariff_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity2_cost",
        translation_key="current_month_high_tariff_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity_cost_merged",
        translation_key="current_month_power_total_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/gas",
        translation_key="current_month_gas_usage",
        icon="mdi:counter",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/gas_cost",
        translation_key="current_month_gas_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/fixed_cost",
        translation_key="current_month_fixed_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/total_cost",
        translation_key="current_month_total_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity1",
        translation_key="current_year_low_tariff_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity2",
        translation_key="current_year_high_tariff_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity1_returned",
        translation_key="current_year_low_tariff_returned",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity2_returned",
        translation_key="current_year_high_tariff_returned",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity_merged",
        translation_key="current_year_power_usage_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity_returned_merged",
        translation_key="current_year_power_returned_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity1_cost",
        translation_key="current_year_low_tariff_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity2_cost",
        translation_key="current_year_high_tariff_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity_cost_merged",
        translation_key="current_year_power_total_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/gas",
        translation_key="current_year_gas_usage",
        icon="mdi:counter",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/gas_cost",
        translation_key="current_year_gas_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/fixed_cost",
        translation_key="current_year_fixed_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/total_cost",
        translation_key="current_year_total_cost",
        icon="mdi:currency-eur",
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/consumption/quarter-hour-peak-electricity/average_delivered",
        translation_key="previous_quarter_hour_peak_usage",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/consumption/quarter-hour-peak-electricity/read_at_start",
        translation_key="quarter_hour_peak_start_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        state=dt_util.parse_datetime,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/consumption/quarter-hour-peak-electricity/read_at_end",
        translation_key="quarter_hour_peak_end_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        state=dt_util.parse_datetime,
    ),
)
