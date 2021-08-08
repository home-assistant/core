"""Constants for the Solar-Log integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import (
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
)

DOMAIN = "solarlog"

"""Default config for solarlog."""
DEFAULT_HOST = "http://solar-log"
DEFAULT_NAME = "solarlog"

"""Fixed constants."""
SCAN_INTERVAL = timedelta(seconds=60)


@dataclass
class SolarlogRequiredKeysMixin:
    """Mixin for required keys."""

    json_key: str


@dataclass
class SolarlogSensorEntityDescription(
    SensorEntityDescription, SolarlogRequiredKeysMixin
):
    """Describes Solarlog sensor entity."""


SENSOR_TYPES: tuple[SolarlogSensorEntityDescription, ...] = (
    SolarlogSensorEntityDescription(
        key="time",
        json_key="TIME",
        name="last update",
        icon="mdi:calendar-clock",
    ),
    SolarlogSensorEntityDescription(
        key="power_ac",
        json_key="powerAC",
        name="power AC",
        unit_of_measurement=POWER_WATT,
        icon="mdi:solar-power",
    ),
    SolarlogSensorEntityDescription(
        key="power_dc",
        json_key="powerDC",
        name="power DC",
        unit_of_measurement=POWER_WATT,
        icon="mdi:solar-power",
    ),
    SolarlogSensorEntityDescription(
        key="voltage_ac",
        json_key="voltageAC",
        name="voltage AC",
        unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    SolarlogSensorEntityDescription(
        key="voltage_dc",
        json_key="voltageDC",
        name="voltage DC",
        unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    SolarlogSensorEntityDescription(
        key="yield_day",
        json_key="yieldDAY",
        name="yield day",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:solar-power",
    ),
    SolarlogSensorEntityDescription(
        key="yield_yesterday",
        json_key="yieldYESTERDAY",
        name="yield yesterday",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:solar-power",
    ),
    SolarlogSensorEntityDescription(
        key="yield_month",
        json_key="yieldMONTH",
        name="yield month",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:solar-power",
    ),
    SolarlogSensorEntityDescription(
        key="yield_year",
        json_key="yieldYEAR",
        name="yield year",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:solar-power",
    ),
    SolarlogSensorEntityDescription(
        key="yield_total",
        json_key="yieldTOTAL",
        name="yield total",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:solar-power",
    ),
    SolarlogSensorEntityDescription(
        key="consumption_ac",
        json_key="consumptionAC",
        name="consumption AC",
        unit_of_measurement=POWER_WATT,
        icon="mdi:power-plug",
    ),
    SolarlogSensorEntityDescription(
        key="consumption_day",
        json_key="consumptionDAY",
        name="consumption day",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:power-plug",
    ),
    SolarlogSensorEntityDescription(
        key="consumption_yesterday",
        json_key="consumptionYESTERDAY",
        name="consumption yesterday",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:power-plug",
    ),
    SolarlogSensorEntityDescription(
        key="consumption_month",
        json_key="consumptionMONTH",
        name="consumption month",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:power-plug",
    ),
    SolarlogSensorEntityDescription(
        key="consumption_year",
        json_key="consumptionYEAR",
        name="consumption year",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:power-plug",
    ),
    SolarlogSensorEntityDescription(
        key="consumption_total",
        json_key="consumptionTOTAL",
        name="consumption total",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:power-plug",
    ),
    SolarlogSensorEntityDescription(
        key="total_power",
        json_key="totalPOWER",
        name="total power",
        unit_of_measurement="Wp",
        icon="mdi:solar-power",
    ),
    SolarlogSensorEntityDescription(
        key="alternator_loss",
        json_key="alternatorLOSS",
        name="alternator loss",
        unit_of_measurement=POWER_WATT,
        icon="mdi:solar-power",
    ),
    SolarlogSensorEntityDescription(
        key="capacity",
        json_key="CAPACITY",
        name="capacity",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:solar-power",
    ),
    SolarlogSensorEntityDescription(
        key="efficiency",
        json_key="EFFICIENCY",
        name="efficiency",
        unit_of_measurement=f"% {POWER_WATT}/{POWER_WATT}p",
        icon="mdi:solar-power",
    ),
    SolarlogSensorEntityDescription(
        key="power_available",
        json_key="powerAVAILABLE",
        name="power available",
        unit_of_measurement=POWER_WATT,
        icon="mdi:solar-power",
    ),
    SolarlogSensorEntityDescription(
        key="usage",
        json_key="USAGE",
        name="usage",
        icon="mdi:solar-power",
    ),
)
