"""Constants for Hunter Douglas Powerview hub."""

from aiohttp.client_exceptions import ServerDisconnectedError
from aiopvapi.helpers.aiorequest import (
    PvApiConnectionError,
    PvApiEmptyData,
    PvApiMaintenance,
    PvApiResponseStatusError,
)

DOMAIN = "hunterdouglas_powerview"
MANUFACTURER = "Hunter Douglas"

REDACT_MAC_ADDRESS = "mac_address"
REDACT_SERIAL_NUMBER = "serial_number"
REDACT_HUB_ADDRESS = "hub_address"

STATE_ATTRIBUTE_ROOM_NAME = "room_name"
STATE_ATTRIBUTE_EXECUTION_TIME = "execution_time"
STATE_ATTRIBUTE_EXECUTION_DAYS = "execution_days"

HUB_EXCEPTIONS = (
    ServerDisconnectedError,
    TimeoutError,
    PvApiConnectionError,
    PvApiResponseStatusError,
    PvApiMaintenance,
    PvApiEmptyData,
)
