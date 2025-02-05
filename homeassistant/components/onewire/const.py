"""Constants for 1-Wire component."""

from __future__ import annotations

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 4304

DOMAIN = "onewire"

DEVICE_KEYS_0_3 = range(4)
DEVICE_KEYS_0_7 = range(8)
DEVICE_KEYS_A_B = ("A", "B")

DEVICE_SUPPORT = {
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
    "A6": (),
    "EF": ("HB_HUB", "HB_MOISTURE_METER", "HobbyBoards_EF"),
}

DEVICE_SUPPORT_OPTIONS = ["28"]

PRECISION_MAPPING_FAMILY_28 = {
    "temperature": "Default",
    "temperature9": "9 Bits",
    "temperature10": "10 Bits",
    "temperature11": "11 Bits",
    "temperature12": "12 Bits",
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
