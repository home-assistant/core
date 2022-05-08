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
from homeassistant.util.dt import as_local

DOMAIN = "sungrow"


@dataclass
class SungrowSensorEntityDescription(SensorEntityDescription):
    """Describes Sungrow sensor entity."""

    value: Callable[[float | int], float] | Callable[[datetime], datetime] | None = None


SENSOR_TYPES: tuple[SungrowSensorEntityDescription, ...] = (
    SungrowSensorEntityDescription(
        key="time",
        name="last update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=as_local,
    ),
    # '5031 - Total active power'
    SungrowSensorEntityDescription(
        key="5031 - Total active power",
        name="power AC",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5017 - Total DC power'
    SungrowSensorEntityDescription(
        key="5017 - Total DC power",
        name="power DC",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5019 - Phase A voltage'
    SungrowSensorEntityDescription(
        key="5019 - Phase A voltage",
        name="voltage AC1",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5020 - Phase B voltage'
    SungrowSensorEntityDescription(
        key="5020 - Phase B voltage",
        name="voltage AC2",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5021 - Phase C voltage'
    SungrowSensorEntityDescription(
        key="5021 - Phase C voltage",
        name="voltage AC3",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5022 - Phase A current'
    SungrowSensorEntityDescription(
        key="5022 - Phase A current",
        name="current AC1",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5023 - Phase B current'
    SungrowSensorEntityDescription(
        key="5023 - Phase B current",
        name="current AC2",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5024 - Phase C current'
    SungrowSensorEntityDescription(
        key="5024 - Phase C current",
        name="current AC3",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5003 - Daily power yields'
    SungrowSensorEntityDescription(
        key="5003 - Daily power yields",
        name="yield day",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value=lambda value: round(value, 3),
    ),
    # '5144 - Total power yields'
    SungrowSensorEntityDescription(
        key="5144 - Total power yields",
        name="yield total",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value=lambda value: round(value, 1),
    ),
    # '5113 - Daily running time'
    SungrowSensorEntityDescription(
        key="5113 - Daily running time",
        name="running time today",
        icon="mdi:solar-power",
        native_unit_of_measurement=TIME_MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
    ),
    # '5006 - Total running time'
    SungrowSensorEntityDescription(
        key="5006 - Total running time",
        name="running time total",
        icon="mdi-clock-start",
        native_unit_of_measurement=TIME_HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        value=lambda value: round(value, 1),
    ),
    # '5001 - Nominal active power'
    SungrowSensorEntityDescription(
        key="5001 - Nominal active power",
        name="installed peak power",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    # '5017 - Total DC power' - '5031 - Total active power'
    SungrowSensorEntityDescription(
        key="alternator_loss",
        name="alternator loss",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # '5035 - Power factor'
    SungrowSensorEntityDescription(
        key="5035 - Power factor",
        name="efficiency",
        icon="mdi-gauge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: round(value / 10, 1),
    ),
    # '5036 - Grid frequency'
    SungrowSensorEntityDescription(
        key="5036 - Grid frequency",
        name="net frequency",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: round(value, 1),
    ),
)
