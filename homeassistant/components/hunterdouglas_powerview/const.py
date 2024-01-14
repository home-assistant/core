"""Constants for Hunter Douglas Powerview hub."""

import asyncio

from aiohttp.client_exceptions import ServerDisconnectedError
from aiopvapi.helpers.aiorequest import (
    PvApiConnectionError,
    PvApiMaintenance,
    PvApiResponseStatusError,
)

DOMAIN = "hunterdouglas_powerview"
MANUFACTURER = "Hunter Douglas"

REDACT_MAC_ADDRESS = "mac_address"
REDACT_SERIAL_NUMBER = "serial_number"
REDACT_HUB_ADDRESS = "hub_address"

STATE_ATTRIBUTE_ROOM_NAME = "room_name"

HUB_EXCEPTIONS = (
    ServerDisconnectedError,
    asyncio.TimeoutError,
    PvApiConnectionError,
    PvApiResponseStatusError,
    PvApiMaintenance,
)
