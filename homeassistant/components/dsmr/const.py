"""Constants for the DSMR integration."""
from __future__ import annotations

import logging

from dsmr_parser import obis_references

from .models import DSMRSensor

DOMAIN = "dsmr"

LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

CONF_DSMR_VERSION = "dsmr_version"
CONF_RECONNECT_INTERVAL = "reconnect_interval"
CONF_PRECISION = "precision"
CONF_TIME_BETWEEN_UPDATE = "time_between_update"

CONF_SERIAL_ID = "serial_id"
CONF_SERIAL_ID_GAS = "serial_id_gas"

DEFAULT_DSMR_VERSION = "2.2"
DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_PRECISION = 3
DEFAULT_RECONNECT_INTERVAL = 30
DEFAULT_TIME_BETWEEN_UPDATE = 30

DATA_LISTENER = "listener"
DATA_TASK = "task"

DEVICE_NAME_ENERGY = "Energy Meter"
DEVICE_NAME_GAS = "Gas Meter"

ICON_GAS = "mdi:fire"
ICON_POWER = "mdi:flash"
ICON_POWER_FAILURE = "mdi:flash-off"
ICON_SWELL_SAG = "mdi:pulse"


SENSORS: list[DSMRSensor] = [
    DSMRSensor(
        name="Power Consumption",
        obis_reference=obis_references.CURRENT_ELECTRICITY_USAGE,
        force_update=True,
    ),
    DSMRSensor(
        name="Power Production",
        obis_reference=obis_references.CURRENT_ELECTRICITY_DELIVERY,
        force_update=True,
    ),
    DSMRSensor(
        name="Power Tariff",
        obis_reference=obis_references.ELECTRICITY_ACTIVE_TARIFF,
    ),
    DSMRSensor(
        name="Energy Consumption (tarif 1)",
        obis_reference=obis_references.ELECTRICITY_USED_TARIFF_1,
        force_update=True,
    ),
    DSMRSensor(
        name="Energy Consumption (tarif 2)",
        obis_reference=obis_references.ELECTRICITY_USED_TARIFF_2,
        force_update=True,
    ),
    DSMRSensor(
        name="Energy Production (tarif 1)",
        obis_reference=obis_references.ELECTRICITY_DELIVERED_TARIFF_1,
        force_update=True,
    ),
    DSMRSensor(
        name="Energy Production (tarif 2)",
        obis_reference=obis_references.ELECTRICITY_DELIVERED_TARIFF_2,
        force_update=True,
    ),
    DSMRSensor(
        name="Power Consumption Phase L1",
        obis_reference=obis_references.INSTANTANEOUS_ACTIVE_POWER_L1_POSITIVE,
    ),
    DSMRSensor(
        name="Power Consumption Phase L2",
        obis_reference=obis_references.INSTANTANEOUS_ACTIVE_POWER_L2_POSITIVE,
    ),
    DSMRSensor(
        name="Power Consumption Phase L3",
        obis_reference=obis_references.INSTANTANEOUS_ACTIVE_POWER_L3_POSITIVE,
    ),
    DSMRSensor(
        name="Power Production Phase L1",
        obis_reference=obis_references.INSTANTANEOUS_ACTIVE_POWER_L1_NEGATIVE,
    ),
    DSMRSensor(
        name="Power Production Phase L2",
        obis_reference=obis_references.INSTANTANEOUS_ACTIVE_POWER_L2_NEGATIVE,
    ),
    DSMRSensor(
        name="Power Production Phase L3",
        obis_reference=obis_references.INSTANTANEOUS_ACTIVE_POWER_L3_NEGATIVE,
    ),
    DSMRSensor(
        name="Short Power Failure Count",
        obis_reference=obis_references.SHORT_POWER_FAILURE_COUNT,
    ),
    DSMRSensor(
        name="Long Power Failure Count",
        obis_reference=obis_references.LONG_POWER_FAILURE_COUNT,
    ),
    DSMRSensor(
        name="Voltage Sags Phase L1",
        obis_reference=obis_references.VOLTAGE_SAG_L1_COUNT,
    ),
    DSMRSensor(
        name="Voltage Sags Phase L2",
        obis_reference=obis_references.VOLTAGE_SAG_L2_COUNT,
    ),
    DSMRSensor(
        name="Voltage Sags Phase L3",
        obis_reference=obis_references.VOLTAGE_SAG_L3_COUNT,
    ),
    DSMRSensor(
        name="Voltage Swells Phase L1",
        obis_reference=obis_references.VOLTAGE_SWELL_L1_COUNT,
    ),
    DSMRSensor(
        name="Voltage Swells Phase L2",
        obis_reference=obis_references.VOLTAGE_SWELL_L2_COUNT,
    ),
    DSMRSensor(
        name="Voltage Swells Phase L3",
        obis_reference=obis_references.VOLTAGE_SWELL_L3_COUNT,
    ),
    DSMRSensor(
        name="Voltage Phase L1",
        obis_reference=obis_references.INSTANTANEOUS_VOLTAGE_L1,
    ),
    DSMRSensor(
        name="Voltage Phase L2",
        obis_reference=obis_references.INSTANTANEOUS_VOLTAGE_L2,
    ),
    DSMRSensor(
        name="Voltage Phase L3",
        obis_reference=obis_references.INSTANTANEOUS_VOLTAGE_L3,
    ),
    DSMRSensor(
        name="Current Phase L1",
        obis_reference=obis_references.INSTANTANEOUS_CURRENT_L1,
    ),
    DSMRSensor(
        name="Current Phase L2",
        obis_reference=obis_references.INSTANTANEOUS_CURRENT_L2,
    ),
    DSMRSensor(
        name="Current Phase L3",
        obis_reference=obis_references.INSTANTANEOUS_CURRENT_L3,
    ),
    DSMRSensor(
        name="Energy Consumption (total)",
        obis_reference=obis_references.LUXEMBOURG_ELECTRICITY_USED_TARIFF_GLOBAL,
        dsmr_versions={"5L"},
        force_update=True,
    ),
    DSMRSensor(
        name="Energy Production (total)",
        obis_reference=obis_references.LUXEMBOURG_ELECTRICITY_DELIVERED_TARIFF_GLOBAL,
        dsmr_versions={"5L"},
        force_update=True,
    ),
    DSMRSensor(
        name="Energy Consumption (total)",
        obis_reference=obis_references.ELECTRICITY_IMPORTED_TOTAL,
        dsmr_versions={"2.2", "4", "5", "5B"},
        force_update=True,
    ),
    DSMRSensor(
        name="Gas Consumption",
        obis_reference=obis_references.HOURLY_GAS_METER_READING,
        dsmr_versions={"4", "5", "5L"},
        force_update=True,
        is_gas=True,
    ),
    DSMRSensor(
        name="Gas Consumption",
        obis_reference=obis_references.BELGIUM_HOURLY_GAS_METER_READING,
        dsmr_versions={"5B"},
        force_update=True,
        is_gas=True,
    ),
    DSMRSensor(
        name="Gas Consumption",
        obis_reference=obis_references.GAS_METER_READING,
        dsmr_versions={"2.2"},
        force_update=True,
        is_gas=True,
    ),
]
