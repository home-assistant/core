"""Constants for 1-Wire component."""
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

CONF_MOUNT_DIR = "mount_dir"
CONF_NAMES = "names"

CONF_TYPE_OWFS = "OWFS"
CONF_TYPE_OWSERVER = "OWServer"
CONF_TYPE_SYSBUS = "SysBus"

DEFAULT_OWSERVER_PORT = 4304
DEFAULT_SYSBUS_MOUNT_DIR = "/sys/bus/w1/devices/"

DOMAIN = "onewire"

PRESSURE_CBAR = "cbar"

SUPPORTED_PLATFORMS = [
    SENSOR_DOMAIN,
]
