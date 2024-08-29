"""Constants for the Mammotion Luba integration."""

import logging
from typing import Final

from bleak_retry_connector import BleakError, BleakNotFoundError
from pymammotion.mammotion.devices.mammotion import CharacteristicMissingError

DOMAIN: Final = "mammotion"

DEVICE_SUPPORT = ("Luba", "Yuka")

ATTR_DIRECTION = "direction"

DEFAULT_RETRY_COUNT = 3
CONF_RETRY_COUNT = "retry_count"
LOGGER: Final = logging.getLogger(__package__)

COMMAND_EXCEPTIONS = (
    BleakNotFoundError,
    CharacteristicMissingError,
    BleakError,
    TimeoutError,
)

CONF_STAY_CONNECTED_BLUETOOTH: Final = "stay_connected_bluetooth"
CONF_ACCOUNTNAME: Final = "account_name"
CONF_USE_WIFI: Final = "use_wifi"
CONF_DEVICE_NAME: Final = "device_name"
CONF_AUTH_DATA: Final = "auth_data"
CONF_AEP_DATA: Final = "aep_data"
CONF_SESSION_DATA: Final = "session_data"
CONF_REGION_DATA: Final = "region_data"
CONF_DEVICE_DATA: Final = "device_data"
