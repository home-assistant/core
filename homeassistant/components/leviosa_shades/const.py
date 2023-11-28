"""Constants for the Leviosa Motor Shades Zone integration."""

import asyncio
from typing import Final

from aiohttp.client_exceptions import (
    ServerConnectionError,
    ServerDisconnectedError,
    ServerTimeoutError,
)

DOMAIN: Final = "leviosa_shades"

MANUFACTURER: Final = "Leviosa Motor Shades LLC"
MODEL: Final = "Zone Hub"
DEVICE_NAME: Final = "device_name"
DEVICE_FW_V: Final = "firmware"
DEVICE_MAC: Final = "device_mac"

BLIND_GROUPS: Final = "blind_groups"
GROUP1_NAME: Final = "grp1_name"
GROUP2_NAME: Final = "grp2_name"
GROUP3_NAME: Final = "grp3_name"
GROUP4_NAME: Final = "grp4_name"
GROUP5_NAME: Final = "grp5_name"
GROUP6_NAME: Final = "grp6_name"

CANNOTCONNECT: Final = "cannot_connect"

HUB_EXCEPTIONS = (
    ServerDisconnectedError,
    asyncio.TimeoutError,
    ServerConnectionError,
    ServerTimeoutError,
)
