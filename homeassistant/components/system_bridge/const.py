"""Constants for the System Bridge integration."""
from aiohttp.client_exceptions import (
    ClientConnectionError,
    ClientConnectorError,
    ClientResponseError,
)
from systembridge.exceptions import BridgeException

DOMAIN = "system_bridge"

BRIDGE_CONNECTION_ERRORS = (
    BridgeException,
    ClientConnectorError,
    ClientConnectionError,
    ClientResponseError,
)
