"""Definitions for DSMR Reader sensors added to MQTT."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntityDescription,
)
from homeassistant.const import (
    CURRENCY_EURO,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_KILO_WATT,
    VOLUME_CUBIC_METERS,
)
from homeassistant.util import dt as dt_util


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
        name="Low tariff usage",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=dt_util.utc_from_timestamp(0),
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/electricity_returned_1",
        name="Low tariff returned",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=dt_util.utc_from_timestamp(0),
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/electricity_delivered_2",
        name="High tariff usage",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=dt_util.utc_from_timestamp(0),
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/electricity_returned_2",
        name="High tariff returned",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=dt_util.utc_from_timestamp(0),
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/electricity_currently_delivered",
        name="Current power usage",
        device_class=DEVICE_CLASS_POWER,
        unit_of_measurement=POWER_KILO_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/electricity_currently_returned",
        name="Current power return",
        device_class=DEVICE_CLASS_POWER,
        unit_of_measurement=POWER_KILO_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_currently_delivered_l1",
        name="Current power usage L1",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_POWER,
        unit_of_measurement=POWER_KILO_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_currently_delivered_l2",
        name="Current power usage L2",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_POWER,
        unit_of_measurement=POWER_KILO_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_currently_delivered_l3",
        name="Current power usage L3",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_POWER,
        unit_of_measurement=POWER_KILO_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_currently_returned_l1",
        name="Current power return L1",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_POWER,
        unit_of_measurement=POWER_KILO_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_currently_returned_l2",
        name="Current power return L2",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_POWER,
        unit_of_measurement=POWER_KILO_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_currently_returned_l3",
        name="Current power return L3",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_POWER,
        unit_of_measurement=POWER_KILO_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/extra_device_delivered",
        name="Gas meter usage",
        entity_registry_enabled_default=False,
        icon="mdi:fire",
        unit_of_measurement=VOLUME_CUBIC_METERS,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=dt_util.utc_from_timestamp(0),
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_voltage_l1",
        name="Current voltage L1",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_VOLTAGE,
        unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_voltage_l2",
        name="Current voltage L2",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_VOLTAGE,
        unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_voltage_l3",
        name="Current voltage L3",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_VOLTAGE,
        unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_power_current_l1",
        name="Phase power current L1",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_CURRENT,
        unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_power_current_l2",
        name="Phase power current L2",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_CURRENT,
        unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/phase_power_current_l3",
        name="Phase power current L3",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_CURRENT,
        unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/reading/timestamp",
        name="Telegram timestamp",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/consumption/gas/delivered",
        name="Gas usage",
        icon="mdi:fire",
        unit_of_measurement=VOLUME_CUBIC_METERS,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=dt_util.utc_from_timestamp(0),
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/consumption/gas/currently_delivered",
        name="Current gas usage",
        icon="mdi:fire",
        unit_of_measurement=VOLUME_CUBIC_METERS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/consumption/gas/read_at",
        name="Gas meter read",
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity1",
        name="Low tariff usage",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=dt_util.utc_from_timestamp(0),
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity2",
        name="High tariff usage",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=dt_util.utc_from_timestamp(0),
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity1_returned",
        name="Low tariff return",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=dt_util.utc_from_timestamp(0),
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity2_returned",
        name="High tariff return",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=dt_util.utc_from_timestamp(0),
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity_merged",
        name="Power usage total",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=dt_util.utc_from_timestamp(0),
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity_returned_merged",
        name="Power return total",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=dt_util.utc_from_timestamp(0),
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity1_cost",
        name="Low tariff cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity2_cost",
        name="High tariff cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/electricity_cost_merged",
        name="Power total cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/gas",
        name="Gas usage",
        icon="mdi:counter",
        unit_of_measurement=VOLUME_CUBIC_METERS,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/gas_cost",
        name="Gas cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/total_cost",
        name="Total cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/energy_supplier_price_electricity_delivered_1",
        name="Low tariff delivered price",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/energy_supplier_price_electricity_delivered_2",
        name="High tariff delivered price",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/energy_supplier_price_electricity_returned_1",
        name="Low tariff returned price",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/energy_supplier_price_electricity_returned_2",
        name="High tariff returned price",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/energy_supplier_price_gas",
        name="Gas price",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/day-consumption/fixed_cost",
        name="Current day fixed cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/dsmr_version",
        name="DSMR version",
        entity_registry_enabled_default=False,
        icon="mdi:alert-circle",
        state=dsmr_transform,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/electricity_tariff",
        name="Electricity tariff",
        icon="mdi:flash",
        state=tariff_transform,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/power_failure_count",
        name="Power failure count",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/long_power_failure_count",
        name="Long power failure count",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/voltage_sag_count_l1",
        name="Voltage sag L1",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/voltage_sag_count_l2",
        name="Voltage sag L2",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/voltage_sag_count_l3",
        name="Voltage sag L3",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/voltage_swell_count_l1",
        name="Voltage swell L1",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/voltage_swell_count_l2",
        name="Voltage swell L2",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/voltage_swell_count_l3",
        name="Voltage swell L3",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/rejected_telegrams",
        name="Rejected telegrams",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity1",
        name="Current month low tariff usage",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity2",
        name="Current month high tariff usage",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity1_returned",
        name="Current month low tariff returned",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity2_returned",
        name="Current month high tariff returned",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity_merged",
        name="Current month power usage total",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity_returned_merged",
        name="Current month power return total",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity1_cost",
        name="Current month low tariff cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity2_cost",
        name="Current month high tariff cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/electricity_cost_merged",
        name="Current month power total cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/gas",
        name="Current month gas usage",
        icon="mdi:counter",
        unit_of_measurement=VOLUME_CUBIC_METERS,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/gas_cost",
        name="Current month gas cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/fixed_cost",
        name="Current month fixed cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-month/total_cost",
        name="Current month total cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity1",
        name="Current year low tariff usage",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity2",
        name="Current year high tariff usage",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity1_returned",
        name="Current year low tariff returned",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity2_returned",
        name="Current year high tariff usage",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity_merged",
        name="Current year power usage total",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity_returned_merged",
        name="Current year power returned total",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity1_cost",
        name="Current year low tariff cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity2_cost",
        name="Current year high tariff cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/electricity_cost_merged",
        name="Current year power total cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/gas",
        name="Current year gas usage",
        icon="mdi:counter",
        unit_of_measurement=VOLUME_CUBIC_METERS,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/gas_cost",
        name="Current year gas cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/fixed_cost",
        name="Current year fixed cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
    DSMRReaderSensorEntityDescription(
        key="dsmr/current-year/total_cost",
        name="Current year total cost",
        icon="mdi:currency-eur",
        unit_of_measurement=CURRENCY_EURO,
    ),
)
