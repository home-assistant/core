"""Constants for 1-Wire component."""
from __future__ import annotations

from homeassistant.const import Platform

CONF_MOUNT_DIR = "mount_dir"

CONF_TYPE_OWSERVER = "OWServer"
CONF_TYPE_SYSBUS = "SysBus"

DEFAULT_OWSERVER_HOST = "localhost"
DEFAULT_OWSERVER_PORT = 4304
DEFAULT_SYSBUS_MOUNT_DIR = "/sys/bus/w1/devices/"

DOMAIN = "onewire"

DEVICE_KEYS_0_3 = range(4)
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
    "30": (),
    "3A": (),
    "3B": (),
    "42": (),
    "7E": ("EDS0066", "EDS0068"),
    "EF": ("HB_HUB", "HB_MOISTURE_METER", "HobbyBoards_EF"),
}
DEVICE_SUPPORT_SYSBUS = ["10", "22", "28", "3B", "42"]

DEVICE_SUPPORT_PRECISION_MAPPING = ["28"]

PRECISION_MAPPING_FAMILY_28 = {
    "Default": "temperature",
    "9 Bits": "temperature9",
    "10 Bits": "temperature10",
    "11 Bits": "temperature11",
    "12 Bits": "temperature12",
}

OPTION_ENTRY_DEVICE_OPTIONS = "device_options"
OPTION_ENTRY_SENSOR_PRECISION = "precision"
INPUT_ENTRY_CLEAR_OPTIONS = "clear_device_options"
INPUT_ENTRY_DEVICE_SELECTION = "device_selection"

MANUFACTURER_MAXIM = "Maxim Integrated"
MANUFACTURER_HOBBYBOARDS = "Hobby Boards"
MANUFACTURER_EDS = "Embedded Data Systems"

READ_MODE_BOOL = "bool"
READ_MODE_FLOAT = "float"
READ_MODE_INT = "int"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]
