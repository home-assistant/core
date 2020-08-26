"""Constants for the deCONZ component."""
import logging

from homeassistant.const import (
    ELECTRICAL_CURRENT_AMPERE,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
    VOLT,
)

LOGGER = logging.getLogger(__package__)

CONF_MOUNT_DIR = "mount_dir"
CONF_NAMES = "names"

DEFAULT_PORT = 4304
DEFAULT_MOUNT_DIR = "/sys/bus/w1/devices/"
DEFAULT_OWFS_MOUNT_DIR = "/mnt/1wire"

SENSOR_TYPES = {
    # SensorType: [ Measured unit, Unit ]
    "temperature": ["temperature", TEMP_CELSIUS],
    "humidity": ["humidity", UNIT_PERCENTAGE],
    "humidity_raw": ["humidity", UNIT_PERCENTAGE],
    "pressure": ["pressure", "mb"],
    "illuminance": ["illuminance", "lux"],
    "wetness_0": ["wetness", UNIT_PERCENTAGE],
    "wetness_1": ["wetness", UNIT_PERCENTAGE],
    "wetness_2": ["wetness", UNIT_PERCENTAGE],
    "wetness_3": ["wetness", UNIT_PERCENTAGE],
    "moisture_0": ["moisture", "cb"],
    "moisture_1": ["moisture", "cb"],
    "moisture_2": ["moisture", "cb"],
    "moisture_3": ["moisture", "cb"],
    "counter_a": ["counter", "count"],
    "counter_b": ["counter", "count"],
    "HobbyBoard": ["none", "none"],
    "voltage": ["voltage", VOLT],
    "voltage_VAD": ["voltage", VOLT],
    "voltage_VDD": ["voltage", VOLT],
    "current": ["current", ELECTRICAL_CURRENT_AMPERE],
}

DOMAIN = "onewire"

SUPPORTED_PLATFORMS = [
    "binary_sensor",
    "sensor",
    "switch",
]
