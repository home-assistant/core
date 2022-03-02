"""Constants for the Iammeter integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ELECTRIC_POTENTIAL_VOLT,
    ELECTRIC_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ,
    POWER_WATT,
)

DOMAIN = "iammeter"

# Default config for iammeter.
DEFAULT_IP = "192.168.2.15"
DEFAULT_NAME = "IamMeter"
DEVICE_3080 = "WEM3080"
DEVICE_3080T = "WEM3080T"
DEVICE_TYPES = [DEVICE_3080, DEVICE_3080T]


@dataclass
class IammeterSensorEntityDescription(SensorEntityDescription):
    """Describes Iammeter sensor entity."""

    value: Callable[[float | int], float] | Callable[[datetime], datetime] | None = None


SENSOR_TYPES_3080: tuple[IammeterSensorEntityDescription, ...] = (
    IammeterSensorEntityDescription(
        key="Voltage",
        name="Voltage",
        icon="mdi:solar-power",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="Current",
        name="Current",
        icon="mdi:solar-power",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="Power",
        name="Power",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="ImportEnergy",
        name="ImportEnergy",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="ExportGrid",
        name="ExportGrid",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)
SENSOR_TYPES_3080T: tuple[IammeterSensorEntityDescription, ...] = (
    IammeterSensorEntityDescription(
        key="Voltage_A",
        name="Voltage_A",
        icon="mdi:solar-power",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="Current_A",
        name="Current_A",
        icon="mdi:solar-power",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="Power_A",
        name="Power_A",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="ImportEnergy_A",
        name="ImportEnergy_A",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="ExportGrid_A",
        name="ExportGrid_A",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="Frequency_A",
        name="Frequency_A",
        icon="mdi:solar-power",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="PF_A",
        name="PF_A",
        icon="mdi:solar-power",
        native_unit_of_measurement="",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="Voltage_B",
        name="Voltage_B",
        icon="mdi:solar-power",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="Current_B",
        name="Current_B",
        icon="mdi:solar-power",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="Power_B",
        name="Power_B",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="ImportEnergy_B",
        name="ImportEnergy_B",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="ExportGrid_B",
        name="ExportGrid_B",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="Frequency_B",
        name="Frequency_B",
        icon="mdi:solar-power",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="PF_B",
        name="PF_B",
        icon="mdi:solar-power",
        native_unit_of_measurement="",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="Voltage_C",
        name="Voltage_C",
        icon="mdi:solar-power",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="Current_C",
        name="Current_C",
        icon="mdi:solar-power",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="Power_C",
        name="Power_C",
        icon="mdi:solar-power",
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="ImportEnergy_C",
        name="ImportEnergy_C",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="ExportGrid_C",
        name="ExportGrid_C",
        icon="mdi:solar-power",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="Frequency_C",
        name="Frequency_C",
        icon="mdi:solar-power",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IammeterSensorEntityDescription(
        key="PF_C",
        name="PF_C",
        icon="mdi:solar-power",
        native_unit_of_measurement="",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)
