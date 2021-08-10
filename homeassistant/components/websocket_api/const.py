"""Websocket constants."""
from __future__ import annotations

import asyncio
from concurrent import futures
from functools import partial
import json
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder

if TYPE_CHECKING:
    from .connection import ActiveConnection


WebSocketCommandHandler = Callable[
    [HomeAssistant, "ActiveConnection", Dict[str, Any]], None
]
AsyncWebSocketCommandHandler = Callable[
    [HomeAssistant, "ActiveConnection", Dict[str, Any]], Awaitable[None]
]

DOMAIN: Final = "websocket_api"
URL: Final = "/api/websocket"
PENDING_MSG_PEAK: Final = 512
PENDING_MSG_PEAK_TIME: Final = 5
MAX_PENDING_MSG: Final = 2048

ERR_ID_REUSE: Final = "id_reuse"
ERR_INVALID_FORMAT: Final = "invalid_format"
ERR_NOT_FOUND: Final = "not_found"
ERR_NOT_SUPPORTED: Final = "not_supported"
ERR_HOME_ASSISTANT_ERROR: Final = "home_assistant_error"
ERR_UNKNOWN_COMMAND: Final = "unknown_command"
ERR_UNKNOWN_ERROR: Final = "unknown_error"
ERR_UNAUTHORIZED: Final = "unauthorized"
ERR_TIMEOUT: Final = "timeout"
ERR_TEMPLATE_ERROR: Final = "template_error"

TYPE_RESULT: Final = "result"

# Define the possible errors that occur when connections are cancelled.
# Originally, this was just asyncio.CancelledError, but issue #9546 showed
# that futures.CancelledErrors can also occur in some situations.
CANCELLATION_ERRORS: Final = (asyncio.CancelledError, futures.CancelledError)

# Event types
SIGNAL_WEBSOCKET_CONNECTED: Final = "websocket_connected"
SIGNAL_WEBSOCKET_DISCONNECTED: Final = "websocket_disconnected"

# Data used to store the current connection list
DATA_CONNECTIONS: Final = f"{DOMAIN}.connections"

JSON_DUMP: Final = partial(json.dumps, cls=JSONEncoder, allow_nan=False)
