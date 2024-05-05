"""Constants for the Vemmio integration."""

import asyncio
from logging import Logger, getLogger
from typing import Final

import aiohttp

DOMAIN = "vemmio"

LOGGER: Logger = getLogger(__package__)

CONNECT_ERRORS = (
    aiohttp.ClientError,
    asyncio.TimeoutError,
    OSError,
)

CONF_REVISION: Final = "revision"

DEFAULT_PORT: Final = 8080
