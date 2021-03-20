"""Constants for the System Bridge integration."""
import asyncio

from aiohttp.client_exceptions import (
    ClientConnectionError,
    ClientConnectorError,
    ClientResponseError,
)
from systembridge.exceptions import BridgeException

DOMAIN = "system_bridge"

BRIDGE_CONNECTION_ERRORS = (
    asyncio.exceptions.TimeoutError,
    BridgeException,
    ClientConnectionError,
    ClientConnectorError,
    ClientResponseError,
)
