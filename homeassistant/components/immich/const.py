"""Constants for the Immich integration."""

import asyncio

import aiohttp

DOMAIN = "immich"

DEFAULT_PORT = 2283
DEFAULT_USE_SSL = False
DEFAULT_VERIFY_SSL = False

CONNECT_ERRORS = (
    aiohttp.ClientError,
    asyncio.TimeoutError,
    OSError,
)
