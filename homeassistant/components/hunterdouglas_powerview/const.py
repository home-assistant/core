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

STATE_ATTRIBUTE_ROOM_NAME = "room_name"

HUB_EXCEPTIONS = (
    ServerDisconnectedError,
    TimeoutError,
    PvApiConnectionError,
    PvApiResponseStatusError,
    PvApiMaintenance,
    PvApiEmptyData,
)
