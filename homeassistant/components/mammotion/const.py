"""Constants for the Mammotion Luba integration."""

import logging
from typing import Final

from bleak.exc import BleakError
from bleak_retry_connector import BleakNotFoundError
from pymammotion.aliyun.cloud_gateway import (
    CheckSessionException,
    DeviceOfflineException,
    SetupException,
)
from pymammotion.mammotion.devices.mammotion_bluetooth import CharacteristicMissingError
from pymammotion.utility.constant import WorkMode

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
    DeviceOfflineException,
)

EXPIRED_CREDENTIAL_EXCEPTIONS = (CheckSessionException, SetupException)

CONF_ACCOUNTNAME: Final = "account_name"
CONF_ACCOUNT_ID: Final = "mammotion_account_id"
CONF_BLE_DEVICES: Final = "ble_devices"
CONF_AUTH_DATA: Final = "auth_data"
CONF_CONNECT_DATA: Final = "connect_data"
CONF_AEP_DATA: Final = "aep_data"
CONF_SESSION_DATA: Final = "session_data"
CONF_REGION_DATA: Final = "region_data"
CONF_DEVICE_DATA: Final = "device_data"
CONF_MAMMOTION_DATA: Final = "mammotion_data"

NO_REQUEST_MODES = (
    WorkMode.MODE_JOB_DRAW,
    WorkMode.MODE_OBSTACLE_DRAW,
    WorkMode.MODE_CHANNEL_DRAW,
    WorkMode.MODE_ERASER_DRAW,
    WorkMode.MODE_UPDATING,
    WorkMode.MODE_EDIT_BOUNDARY,
    WorkMode.MODE_UPDATING,
    WorkMode.MODE_LOCK,
    WorkMode.MODE_MANUAL_MOWING,
)
