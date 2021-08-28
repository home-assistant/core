"""Constants for the Solar-Log integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
)

DOMAIN = "solarlog"

# Default config for solarlog.
DEFAULT_HOST = "http://solar-log"
DEFAULT_NAME = "solarlog"


@dataclass
class SolarlogRequiredKeysMixin:
    """Mixin for required keys."""

    json_key: str


@dataclass
class SolarLogSensorEntityDescription(
    SensorEntityDescription, SolarlogRequiredKeysMixin
):
    """Describes Solarlog sensor entity."""


SENSOR_TYPES: tuple[SolarLogSensorEntityDescription, ...] = (
    SolarLogSensorEntityDescription(
        key="time",
        json_key="TIME",
        name="last update",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SolarLogSensorEntityDescription(
        key="power_ac",
        json_key="powerAC",
        name="power AC",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="power_dc",
        json_key="powerDC",
        name="power DC",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="voltage_ac",
        json_key="voltageAC",
        name="voltage AC",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="voltage_dc",
        json_key="voltageDC",
        name="voltage DC",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="yield_day",
        json_key="yieldDAY",
        name="yield day",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    SolarLogSensorEntityDescription(
        key="yield_yesterday",
        json_key="yieldYESTERDAY",
        name="yield yesterday",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    SolarLogSensorEntityDescription(
        key="yield_month",
        json_key="yieldMONTH",
        name="yield month",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    SolarLogSensorEntityDescription(
        key="yield_year",
        json_key="yieldYEAR",
        name="yield year",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    SolarLogSensorEntityDescription(
        key="yield_total",
        json_key="yieldTOTAL",
        name="yield total",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_ac",
        json_key="consumptionAC",
        name="consumption AC",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_day",
        json_key="consumptionDAY",
        name="consumption day",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_yesterday",
        json_key="consumptionYESTERDAY",
        name="consumption yesterday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_month",
        json_key="consumptionMONTH",
        name="consumption month",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_year",
        json_key="consumptionYEAR",
        name="consumption year",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_total",
        json_key="consumptionTOTAL",
        name="consumption total",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SolarLogSensorEntityDescription(
        key="total_power",
        json_key="totalPOWER",
        name="installed peak power",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    SolarLogSensorEntityDescription(
        key="alternator_loss",
        json_key="alternatorLOSS",
        name="alternator loss",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="capacity",
        json_key="CAPACITY",
        name="capacity",
        icon="mdi:solar-power",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="efficiency",
        json_key="EFFICIENCY",
        name="efficiency",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="power_available",
        json_key="powerAVAILABLE",
        name="power available",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="usage",
        json_key="USAGE",
        name="usage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)
