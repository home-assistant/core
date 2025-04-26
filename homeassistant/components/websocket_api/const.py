"""Websocket constants."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import VolSchemaType
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .connection import ActiveConnection


class WebSocketCommandHandler(Protocol):
    """Protocol for websocket command handler."""

    def __call__(
        self, hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        """Handle a websocket command."""


class WebSocketCommandHandlerWithCommandSchema(WebSocketCommandHandler):
    """Protocol for websocket command handler with internal attributes."""

    _ws_command: str
    _ws_schema: VolSchemaType | Literal[False]


type AsyncWebSocketCommandHandler = Callable[
    [HomeAssistant, ActiveConnection, dict[str, Any]], Awaitable[None]
]

DOMAIN: Final = "websocket_api"
DATA_DOMAIN: HassKey[
    dict[str, tuple[WebSocketCommandHandler, VolSchemaType | Literal[False]]]
] = HassKey(DOMAIN)
URL: Final = "/api/websocket"
PENDING_MSG_PEAK: Final = 1024
PENDING_MSG_PEAK_TIME: Final = 10
# Maximum number of messages that can be pending at any given time.
# This is effectively the upper limit of the number of entities
# that can fire state changes within ~1 second.
# Ideally we would use homeassistant.const.MAX_EXPECTED_ENTITY_IDS
# but since chrome will lock up with too many messages we need to
# limit it to a lower number.
MAX_PENDING_MSG: Final = 4096

# Maximum number of messages that are pending before we force
# resolve the ready future.
PENDING_MSG_MAX_FORCE_READY: Final = 256

ERR_ID_REUSE: Final = "id_reuse"
ERR_INVALID_FORMAT: Final = "invalid_format"
ERR_NOT_ALLOWED: Final = "not_allowed"
ERR_NOT_FOUND: Final = "not_found"
ERR_NOT_SUPPORTED: Final = "not_supported"
ERR_HOME_ASSISTANT_ERROR: Final = "home_assistant_error"
ERR_SERVICE_VALIDATION_ERROR: Final = "service_validation_error"
ERR_UNKNOWN_COMMAND: Final = "unknown_command"
ERR_UNKNOWN_ERROR: Final = "unknown_error"
ERR_UNAUTHORIZED: Final = "unauthorized"
ERR_TIMEOUT: Final = "timeout"
ERR_TEMPLATE_ERROR: Final = "template_error"

TYPE_RESULT: Final = "result"


# Event types
SIGNAL_WEBSOCKET_CONNECTED: Final = "websocket_connected"
SIGNAL_WEBSOCKET_DISCONNECTED: Final = "websocket_disconnected"

# Data used to store the current connection list
DATA_CONNECTIONS: Final = f"{DOMAIN}.connections"

FEATURE_COALESCE_MESSAGES = "coalesce_messages"
