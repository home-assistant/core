"""Constants for the Mammotion Luba integration."""

import logging
from typing import Final

from bleak.exc import BleakError
from bleak_retry_connector import BleakNotFoundError
from pymammotion.aliyun.exceptions import (
    CheckSessionException,
    CloudSetupError,
    DeviceOfflineException,
)
from pymammotion.transport.base import NoTransportAvailableError

DOMAIN: Final = "mammotion"

DEVICE_SUPPORT = ("Luba", "Yuka")

LOGGER: Final = logging.getLogger(__package__)

COMMAND_EXCEPTIONS = (
    BleakNotFoundError,
    BleakError,
    NoTransportAvailableError,
    TimeoutError,
    DeviceOfflineException,
)

EXPIRED_CREDENTIAL_EXCEPTIONS = (CheckSessionException, CloudSetupError)

CONF_ACCOUNTNAME: Final = "account_name"
CONF_ACCOUNT_ID: Final = "mammotion_account_id"
CONF_BLE_DEVICES: Final = "ble_devices"
CONF_AUTH_DATA: Final = "auth_data"
CONF_CONNECT_DATA: Final = "connect_response"
CONF_AEP_DATA: Final = "aep_data"
CONF_SESSION_DATA: Final = "session_data"
CONF_REGION_DATA: Final = "region_data"
CONF_DEVICE_DATA: Final = "device_data"
CONF_MAMMOTION_DATA: Final = "mammotion_data"
CONF_MAMMOTION_MQTT: Final = "mammotion_mqtt"
CONF_MAMMOTION_DEVICE_RECORDS: Final = "mammotion_device_records"
