"""Constants for the Livisi Smart Home integration."""
import logging
from typing import Final

LOGGER = logging.getLogger(__package__)
DOMAIN = "livisi"

CONF_HOST = "host"
CONF_PASSWORD: Final = "password"
CONF_OS_VERSION = "os_version"
AVATAR_PORT: Final = "9090"
CLASSIC_PORT: Final = "8080"
DEVICE_POLLING_DELAY: Final = 60
LIVISI_STATE_CHANGE: Final = "livisi_state_change"
LIVISI_REACHABILITY_CHANGE: Final = "livisi_reachability_change"
ID: Final = "id"
STATE: Final = "state"
IS_REACHABLE: Final = "is_reachable"

SWITCH_PLATFORM: Final = "switch"

PSS_DEVICE_TYPE: Final = "PSS"
