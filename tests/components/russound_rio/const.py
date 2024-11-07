"""Constants for russound_rio tests."""

from collections import namedtuple

HOST = "127.0.0.1"
PORT = 9621
MODEL = "MCA-C5"
HARDWARE_MAC = "00:11:22:33:44:55"

MOCK_CONFIG = {
    "host": HOST,
    "port": PORT,
}

_CONTROLLER = namedtuple("Controller", ["mac_address", "controller_type"])  # noqa: PYI024
MOCK_CONTROLLERS = {1: _CONTROLLER(mac_address=HARDWARE_MAC, controller_type=MODEL)}
