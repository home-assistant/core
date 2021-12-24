"""Constants for the Solar-Log integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
)
from homeassistant.util.dt import as_local

DOMAIN = "solarlog"

# Default config for solarlog.
DEFAULT_HOST = "http://solar-log"
DEFAULT_NAME = "solarlog"


@dataclass
class SolarLogSensorEntityDescription(SensorEntityDescription):
    """Describes Solarlog sensor entity."""

    value: Callable[[float | int], float] | Callable[[datetime], datetime] | None = None


SENSOR_TYPES: tuple[SolarLogSensorEntityDescription, ...] = (
    SolarLogSensorEntityDescription(
        key="time",
        name="last update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=as_local,
    ),
    SolarLogSensorEntityDescription(
        key="power_ac",
        name="power AC",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="power_dc",
        name="power DC",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="voltage_ac",
        name="voltage AC",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="voltage_dc",
        name="voltage DC",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="yield_day",
        name="yield day",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_yesterday",
        name="yield yesterday",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_month",
        name="yield month",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_year",
        name="yield year",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="yield_total",
        name="yield total",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_ac",
        name="consumption AC",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_day",
        name="consumption day",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_yesterday",
        name="consumption yesterday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_month",
        name="consumption month",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_year",
        name="consumption year",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="consumption_total",
        name="consumption total",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value=lambda value: round(value / 1000, 3),
    ),
    SolarLogSensorEntityDescription(
        key="total_power",
        name="installed peak power",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SolarLogSensorEntityDescription(
        key="alternator_loss",
        name="alternator loss",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="capacity",
        name="capacity",
        icon="mdi:solar-power",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: round(value * 100, 1),
    ),
    SolarLogSensorEntityDescription(
        key="efficiency",
        name="efficiency",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: round(value * 100, 1),
    ),
    SolarLogSensorEntityDescription(
        key="power_available",
        name="power available",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="usage",
        name="usage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: round(value * 100, 1),
    ),
)
