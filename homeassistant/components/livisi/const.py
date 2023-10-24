"""Constants for the Livisi Smart Home integration."""
import logging
from typing import Final

LOGGER = logging.getLogger(__package__)
DOMAIN = "livisi"

CONF_HOST = "host"
CONF_PASSWORD: Final = "password"
AVATAR = "Avatar"
AVATAR_PORT: Final = 9090
CLASSIC_PORT: Final = 8080
DEVICE_POLLING_DELAY: Final = 60
LIVISI_STATE_CHANGE: Final = "livisi_state_change"
LIVISI_SHUTTERSTATE_CHANGE: Final = "livisi_shutterstate_change"
LIVISI_FETCH_CURRENT_STATE: Final = "livisi_fetch_current_state"
LIVISI_REACHABILITY_CHANGE: Final = "livisi_reachability_change"
LIVISI_NAMESPACE_CORE: Final = "core.RWE"
LIVISI_NAMESPACE_COSIP: Final = "CosipDevices.RWE"

SWITCH_DEVICE_TYPES: Final = ["ISS", "ISS2", "PSS", "PSSO"]
VRCC_DEVICE_TYPE: Final = "VRCC"
WDS_DEVICE_TYPE: Final = "WDS"
SHUTTER_DEVICE_TYPE: Final = "ISR2"


MAX_TEMPERATURE: Final = 30.0
MIN_TEMPERATURE: Final = 6.0
