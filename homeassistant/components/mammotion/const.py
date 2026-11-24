"""Constants for the Mammotion Luba integration."""

import logging
from typing import Final

from aiohttp import ClientError
from pymammotion.aliyun.exceptions import (
    DeviceOfflineException,
    DeviceUnboundException,
    FailedRequestException,
    GatewayTimeoutException,
    TooManyRequestsException,
)
from pymammotion.transport.base import TransportError

from .exceptions import CommandFailedError

DOMAIN: Final = "mammotion"

DEVICE_SUPPORT = ("Luba", "Yuka")

LOGGER: Final = logging.getLogger(__package__)

# What a user-priority send or state wait raises when the command did not land.
# TransportError covers NoTransportAvailableError, TransportRateLimitedError,
# AccountInUseError and AuthError.
COMMAND_EXCEPTIONS = (
    ClientError,
    CommandFailedError,
    DeviceOfflineException,
    DeviceUnboundException,
    FailedRequestException,
    GatewayTimeoutException,
    TimeoutError,
    TooManyRequestsException,
    TransportError,
)

CONF_ACCOUNTNAME: Final = "account_name"
CONF_ACCOUNT_ID: Final = "mammotion_account_id"
CONF_BLE_DEVICES: Final = "ble_devices"
CONF_AEP_DATA: Final = "aep_data"
CONF_MAMMOTION_MQTT: Final = "mammotion_mqtt"
CONF_MAMMOTION_DEVICE_RECORDS: Final = "mammotion_device_records"
