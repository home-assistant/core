"""Websocket constants."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from concurrent import futures
from typing import TYPE_CHECKING, Any, Final

from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from .connection import ActiveConnection  # noqa: F401


WebSocketCommandHandler = Callable[
    [HomeAssistant, "ActiveConnection", dict[str, Any]], None
]
AsyncWebSocketCommandHandler = Callable[
    [HomeAssistant, "ActiveConnection", dict[str, Any]], Awaitable[None]
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

COMPRESSED_STATE_STATE = "s"
COMPRESSED_STATE_ATTRIBUTES = "a"
COMPRESSED_STATE_CONTEXT = "c"
COMPRESSED_STATE_LAST_CHANGED = "lc"
COMPRESSED_STATE_LAST_UPDATED = "lu"
