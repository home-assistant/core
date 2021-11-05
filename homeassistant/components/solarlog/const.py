"""Constants for the Solar-Log integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL,
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
class SolarLogSensorEntityDescription(SensorEntityDescription):
    """Describes Solarlog sensor entity."""

    factor: float | None = None


SENSOR_TYPES: tuple[SolarLogSensorEntityDescription, ...] = (
    SolarLogSensorEntityDescription(
        key="time",
        name="last update",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SolarLogSensorEntityDescription(
        key="power_ac",
        name="power AC",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="power_dc",
        name="power DC",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="voltage_ac",
        name="voltage AC",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="voltage_dc",
        name="voltage DC",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="yield_day",
        name="yield day",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        factor=0.001,
    ),
    SolarLogSensorEntityDescription(
        key="yield_yesterday",
        name="yield yesterday",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        factor=0.001,
    ),
    SolarLogSensorEntityDescription(
        key="yield_month",
        name="yield month",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        factor=0.001,
    ),
    SolarLogSensorEntityDescription(
        key="yield_year",
        name="yield year",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        factor=0.001,
    ),
    SolarLogSensorEntityDescription(
        key="yield_total",
        name="yield total",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_TOTAL,
        factor=0.001,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_ac",
        name="consumption AC",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_day",
        name="consumption day",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        factor=0.001,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_yesterday",
        name="consumption yesterday",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        factor=0.001,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_month",
        name="consumption month",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        factor=0.001,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_year",
        name="consumption year",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        factor=0.001,
    ),
    SolarLogSensorEntityDescription(
        key="consumption_total",
        name="consumption total",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
        factor=0.001,
    ),
    SolarLogSensorEntityDescription(
        key="total_power",
        name="installed peak power",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    SolarLogSensorEntityDescription(
        key="alternator_loss",
        name="alternator loss",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="capacity",
        name="capacity",
        icon="mdi:solar-power",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
        factor=100,
    ),
    SolarLogSensorEntityDescription(
        key="efficiency",
        name="efficiency",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
        factor=100,
    ),
    SolarLogSensorEntityDescription(
        key="power_available",
        name="power available",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SolarLogSensorEntityDescription(
        key="usage",
        name="usage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
        factor=100,
    ),
)
