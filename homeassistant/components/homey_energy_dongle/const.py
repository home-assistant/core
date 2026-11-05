"""Constants for the Homey Energy Dongle integration."""

DOMAIN = "homey_energy_dongle"

CONF_WS_PATH = "ws_path"
CONF_DSMR_VERSION = "dsmr_version"

DEFAULT_PORT = 80
DEFAULT_WS_PATH = "/ws"

# dsmr-parser names the meter's identifier differently per profile.
IDENTIFIER_FIELDS = (
    "EQUIPMENT_IDENTIFIER",
    "BELGIUM_EQUIPMENT_IDENTIFIER",
    "LUXEMBOURG_EQUIPMENT_IDENTIFIER",
    "Q3D_EQUIPMENT_IDENTIFIER",
)
