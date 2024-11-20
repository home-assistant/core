"""Constants for russound_rio tests."""

from collections import namedtuple

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN

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

DEVICE_NAME = "mca_c5"
NAME_ZONE_1 = "backyard"
ENTITY_ID_ZONE_1 = f"{MP_DOMAIN}.{DEVICE_NAME}_{NAME_ZONE_1}"
