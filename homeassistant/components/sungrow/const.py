"""Constants for the Sungrow Solar Energy integration."""
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
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_KILO_WATT,
    POWER_WATT,
    TIME_HOURS,
    TIME_MINUTES,
)

DOMAIN = "sungrow"

SERIAL_NUMBER = "4990 ~ 4999 - Serial number"
TOTAL_ACTIVE_POWER = "5031 - Total active power"
TOTAL_DC_POWER = "5017 - Total DC power"
PHASE_A_VOLTAGE = "5019 - Phase A voltage"
PHASE_B_VOLTAGE = "5020 - Phase B voltage"
PHASE_C_VOLTAGE = "5021 - Phase C voltage"
PHASE_A_CURRENT = "5022 - Phase A current"
PHASE_B_CURRENT = "5023 - Phase B current"
PHASE_C_CURRENT = "5024 - Phase C current"
DAILY_POWER_YIELDS = "5003 - Daily power yields"
TOTAL_POWER_YIELDS = "5144 - Total power yields"
DAILY_RUNNING_TIME = "5113 - Daily running time"
TOTAL_RUNNING_TIME = "5006 - Total running time"
NOMINAL_ACTIVE_POWER = "5001 - Nominal active power"
POWER_FACTOR = "5035 - Power factor"
GRID_FREQUENCY = "5036 - Grid frequency"
ALTERNATOR_LOSS = "alternator_loss"


@dataclass
class SungrowSensorEntityDescription(SensorEntityDescription):
    """Describes Sungrow sensor entity."""

    value: Callable[[float | int], float] | Callable[[datetime], datetime] | None = None


SENSOR_TYPES: tuple[SungrowSensorEntityDescription, ...] = (
    # '5031 - Total active power'
    SungrowSensorEntityDescription(
        key=TOTAL_ACTIVE_POWER,
        name="power AC",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5017 - Total DC power'
    SungrowSensorEntityDescription(
        key=TOTAL_DC_POWER,
        name="power DC",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5019 - Phase A voltage'
    SungrowSensorEntityDescription(
        key=PHASE_A_VOLTAGE,
        name="voltage AC1",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5020 - Phase B voltage'
    SungrowSensorEntityDescription(
        key=PHASE_B_VOLTAGE,
        name="voltage AC2",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5021 - Phase C voltage'
    SungrowSensorEntityDescription(
        key=PHASE_C_VOLTAGE,
        name="voltage AC3",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5022 - Phase A current'
    SungrowSensorEntityDescription(
        key=PHASE_A_CURRENT,
        name="current AC1",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5023 - Phase B current'
    SungrowSensorEntityDescription(
        key=PHASE_B_CURRENT,
        name="current AC2",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5024 - Phase C current'
    SungrowSensorEntityDescription(
        key=PHASE_C_CURRENT,
        name="current AC3",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5003 - Daily power yields'
    SungrowSensorEntityDescription(
        key=DAILY_POWER_YIELDS,
        name="yield day",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value, 1),
    ),
    # '5144 - Total power yields'
    SungrowSensorEntityDescription(
        key=TOTAL_POWER_YIELDS,
        name="yield total",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value=lambda value: round(value, 1),
    ),
    # '5113 - Daily running time'
    SungrowSensorEntityDescription(
        key=DAILY_RUNNING_TIME,
        name="running time today",
        icon="mdi:solar-power",
        native_unit_of_measurement=TIME_MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
    ),
    # '5006 - Total running time'
    SungrowSensorEntityDescription(
        key=TOTAL_RUNNING_TIME,
        name="running time total",
        icon="mdi-clock-start",
        native_unit_of_measurement=TIME_HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        value=lambda value: round(value, 1),
    ),
    # '5001 - Nominal active power'
    SungrowSensorEntityDescription(
        key=NOMINAL_ACTIVE_POWER,
        name="installed peak power",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    # '5017 - Total DC power' - '5031 - Total active power'
    SungrowSensorEntityDescription(
        key=ALTERNATOR_LOSS,
        name="alternator loss",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5035 - Power factor'
    SungrowSensorEntityDescription(
        key=POWER_FACTOR,
        name="power factor",
        icon="mdi-gauge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: round(value / 10, 1),
    ),
    # '5036 - Grid frequency'
    SungrowSensorEntityDescription(
        key=GRID_FREQUENCY,
        name="net frequency",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: round(value, 1),
    ),
)
