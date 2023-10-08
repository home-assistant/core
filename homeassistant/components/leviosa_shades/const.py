"""Constants for the Leviosa Motor Shades Zone integration."""

import asyncio

from aiohttp.client_exceptions import (
    ServerConnectionError,
    ServerDisconnectedError,
    ServerTimeoutError,
)

DOMAIN = "leviosa_shades"

MANUFACTURER = "Leviosa Motor Shades LLC"
MODEL = "Zone Hub"
DEVICE_NAME = "device_name"
DEVICE_FW_V = "firmware"
DEVICE_MAC = "device_mac"

BLIND_GROUPS = "blind_groups"
GROUP1_NAME = "grp1_name"
GROUP2_NAME = "grp2_name"
GROUP3_NAME = "grp3_name"
GROUP4_NAME = "grp4_name"
GROUP5_NAME = "grp5_name"
GROUP6_NAME = "grp6_name"

SERVICE_NEXT_DOWN_POS = "next_down_pos"
SERVICE_NEXT_UP_POS = "next_up_pos"

CANNOTCONNECT = "cannot_connect"

HUB_EXCEPTIONS = (
    ServerDisconnectedError,
    asyncio.TimeoutError,
    ServerConnectionError,
    ServerTimeoutError,
)
