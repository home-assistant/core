"""Constants for 1-Wire component."""
from __future__ import annotations

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN

CONF_MOUNT_DIR = "mount_dir"
CONF_NAMES = "names"

CONF_TYPE_OWSERVER = "OWServer"
CONF_TYPE_SYSBUS = "SysBus"

DEFAULT_OWSERVER_HOST = "localhost"
DEFAULT_OWSERVER_PORT = 4304
DEFAULT_SYSBUS_MOUNT_DIR = "/sys/bus/w1/devices/"

DOMAIN = "onewire"

DEVICE_KEYS_0_7 = range(8)
DEVICE_KEYS_A_B = ("A", "B")

DEVICE_SUPPORT_OWSERVER = {
    "05": (),
    "10": (),
    "12": (),
    "1D": (),
    "1F": (),
    "22": (),
    "26": (),
    "28": (),
    "29": (),
    "3A": (),
    "3B": (),
    "42": (),
    "7E": ("EDS0066", "EDS0068"),
    "EF": ("HB_MOISTURE_METER", "HobbyBoards_EF"),
}
DEVICE_SUPPORT_SYSBUS = ["10", "22", "28", "3B", "42"]


MANUFACTURER_MAXIM = "Maxim Integrated"
MANUFACTURER_HOBBYBOARDS = "Hobby Boards"
MANUFACTURER_EDS = "Embedded Data Systems"

READ_MODE_BOOL = "bool"
READ_MODE_FLOAT = "float"
READ_MODE_INT = "int"

PLATFORMS = [
    BINARY_SENSOR_DOMAIN,
    SENSOR_DOMAIN,
    SWITCH_DOMAIN,
]
