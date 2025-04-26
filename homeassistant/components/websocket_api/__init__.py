"""WebSocket based API for Home Assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal, cast

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, VolSchemaType
from homeassistant.loader import bind_hass

from . import commands, connection, const, decorators, http, messages  # noqa: F401
from .connection import ActiveConnection, current_connection  # noqa: F401
from .const import (  # noqa: F401
    ERR_HOME_ASSISTANT_ERROR,
    ERR_INVALID_FORMAT,
    ERR_NOT_ALLOWED,
    ERR_NOT_FOUND,
    ERR_NOT_SUPPORTED,
    ERR_SERVICE_VALIDATION_ERROR,
    ERR_TEMPLATE_ERROR,
    ERR_TIMEOUT,
    ERR_UNAUTHORIZED,
    ERR_UNKNOWN_COMMAND,
    ERR_UNKNOWN_ERROR,
    TYPE_RESULT,
    AsyncWebSocketCommandHandler,
    WebSocketCommandHandler,
)
from .decorators import (  # noqa: F401
    async_response,
    require_admin,
    websocket_command,
    ws_require_user,
)
from .messages import (  # noqa: F401
    BASE_COMMAND_MESSAGE_SCHEMA,
    error_message,
    event_message,
    result_message,
)

DOMAIN: Final = const.DOMAIN

DEPENDENCIES: Final[tuple[str]] = ("http",)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@bind_hass
@callback
def async_register_command(
    hass: HomeAssistant,
    command_or_handler: str | const.WebSocketCommandHandler,
    handler: const.WebSocketCommandHandler | None = None,
    schema: VolSchemaType | Literal[False] | None = None,
) -> None:
    """Register a websocket command."""
    if handler is None:
        handler = cast(
            const.WebSocketCommandHandlerWithCommandSchema, command_or_handler
        )
        command = handler._ws_command  # noqa: SLF001
        schema = handler._ws_schema  # noqa: SLF001
    else:
        if TYPE_CHECKING:
            assert isinstance(command_or_handler, str)
        command = command_or_handler
    if (handlers := hass.data.get(const.DATA_DOMAIN)) is None:
        handlers = hass.data[const.DATA_DOMAIN] = {}
    handlers[command] = (handler, False if schema is None else schema)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the websocket API."""
    hass.http.register_view(http.WebsocketAPIView())
    commands.async_register_commands(hass, async_register_command)
    return True
