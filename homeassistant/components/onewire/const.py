"""Constants for 1-Wire component."""
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRICAL_CURRENT_AMPERE,
    LIGHT_LUX,
    PERCENTAGE,
    PRESSURE_MBAR,
    TEMP_CELSIUS,
    VOLT,
)

CONF_MOUNT_DIR = "mount_dir"
CONF_NAMES = "names"

CONF_TYPE_OWFS = "OWFS"
CONF_TYPE_OWSERVER = "OWServer"
CONF_TYPE_SYSBUS = "SysBus"

DEFAULT_OWSERVER_HOST = "localhost"
DEFAULT_OWSERVER_PORT = 4304
DEFAULT_SYSBUS_MOUNT_DIR = "/sys/bus/w1/devices/"

DOMAIN = "onewire"

PRESSURE_CBAR = "cbar"

SENSOR_TYPES = {
    # SensorType: [ Measured unit, Unit, DeviceClass ]
    "temperature": ["temperature", TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE],
    "humidity": ["humidity", PERCENTAGE, DEVICE_CLASS_HUMIDITY],
    "humidity_hih3600": ["humidity", PERCENTAGE, DEVICE_CLASS_HUMIDITY],
    "humidity_hih4000": ["humidity", PERCENTAGE, DEVICE_CLASS_HUMIDITY],
    "humidity_hih5030": ["humidity", PERCENTAGE, DEVICE_CLASS_HUMIDITY],
    "humidity_htm1735": ["humidity", PERCENTAGE, DEVICE_CLASS_HUMIDITY],
    "humidity_raw": ["humidity", PERCENTAGE, DEVICE_CLASS_HUMIDITY],
    "pressure": ["pressure", PRESSURE_MBAR, DEVICE_CLASS_PRESSURE],
    "illuminance": ["illuminance", LIGHT_LUX, DEVICE_CLASS_ILLUMINANCE],
    "wetness_0": ["wetness", PERCENTAGE, DEVICE_CLASS_HUMIDITY],
    "wetness_1": ["wetness", PERCENTAGE, DEVICE_CLASS_HUMIDITY],
    "wetness_2": ["wetness", PERCENTAGE, DEVICE_CLASS_HUMIDITY],
    "wetness_3": ["wetness", PERCENTAGE, DEVICE_CLASS_HUMIDITY],
    "moisture_0": ["moisture", PRESSURE_CBAR, DEVICE_CLASS_PRESSURE],
    "moisture_1": ["moisture", PRESSURE_CBAR, DEVICE_CLASS_PRESSURE],
    "moisture_2": ["moisture", PRESSURE_CBAR, DEVICE_CLASS_PRESSURE],
    "moisture_3": ["moisture", PRESSURE_CBAR, DEVICE_CLASS_PRESSURE],
    "counter_a": ["counter", "count", None],
    "counter_b": ["counter", "count", None],
    "HobbyBoard": ["none", "none", None],
    "voltage": ["voltage", VOLT, DEVICE_CLASS_VOLTAGE],
    "voltage_VAD": ["voltage", VOLT, DEVICE_CLASS_VOLTAGE],
    "voltage_VDD": ["voltage", VOLT, DEVICE_CLASS_VOLTAGE],
    "current": ["current", ELECTRICAL_CURRENT_AMPERE, DEVICE_CLASS_CURRENT],
}

SUPPORTED_PLATFORMS = [
    SENSOR_DOMAIN,
]
