"""Constants for the IoTaWatt integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    FREQUENCY_HERTZ,
    POWER_VOLT_AMPERE,
    POWER_WATT,
)

DEFAULT_ICON = "mdi:flash"
DEFAULT_SCAN_INTERVAL = 30
DOMAIN = "iotawatt"
COORDINATOR = "coordinator"
SIGNAL_ADD_DEVICE = "iotawatt_add_device"

POWER_FACTOR = "PF"
VOLT_AMPERE_REACTIVE = "VAR"
VOLT_AMPERE_REACTIVE_HOURS = "VARh"

ENTITY_DESCRIPTION_KEY_MAP: dict[str, SensorEntityDescription] = {
    "Amps": SensorEntityDescription(
        "Amps",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "Hz": SensorEntityDescription(
        "Hz",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "PF": SensorEntityDescription(
        "PF",
        native_unit_of_measurement=POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_POWER_FACTOR,
    ),
    "Watts": SensorEntityDescription(
        "Watts",
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_POWER,
    ),
    "WattHours": SensorEntityDescription(
        "WattHours",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    "VA": SensorEntityDescription(
        "VA",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_CURRENT,
    ),
    "VAR": SensorEntityDescription(
        "VAR",
        native_unit_of_measurement=VOLT_AMPERE_REACTIVE,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_CURRENT,
    ),
    "VARh": SensorEntityDescription(
        "VARh",
        native_unit_of_measurement=VOLT_AMPERE_REACTIVE_HOURS,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    "Volts": SensorEntityDescription(
        "Volts",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_VOLTAGE,
    ),
}
