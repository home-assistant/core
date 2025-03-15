"""Constants for russound_rio tests."""

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

MODEL = "MCA-C5"
HARDWARE_MAC = "00:11:22:33:44:55"
API_VERSION = "1.08.00"

MOCK_CONFIG = {
    CONF_HOST: "192.168.20.75",
    CONF_PORT: 9621,
}

MOCK_RECONFIGURATION_CONFIG = {
    CONF_HOST: "192.168.20.70",
    CONF_PORT: 9622,
}

DEVICE_NAME = "mca_c5"
NAME_ZONE_1 = "backyard"
ENTITY_ID_ZONE_1 = f"{MP_DOMAIN}.{DEVICE_NAME}_{NAME_ZONE_1}"
