"""WebSocket based API for Home Assistant."""
from __future__ import annotations

from typing import cast

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import bind_hass

from . import commands, connection, const, decorators, http, messages  # noqa: F401
from .connection import ActiveConnection  # noqa: F401
from .const import (  # noqa: F401
    ERR_HOME_ASSISTANT_ERROR,
    ERR_INVALID_FORMAT,
    ERR_NOT_FOUND,
    ERR_NOT_SUPPORTED,
    ERR_TEMPLATE_ERROR,
    ERR_TIMEOUT,
    ERR_UNAUTHORIZED,
    ERR_UNKNOWN_COMMAND,
    ERR_UNKNOWN_ERROR,
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

# mypy: allow-untyped-calls, allow-untyped-defs

DOMAIN = const.DOMAIN

DEPENDENCIES = ("http",)


@bind_hass
@callback
def async_register_command(
    hass: HomeAssistant,
    command_or_handler: str | const.WebSocketCommandHandler,
    handler: const.WebSocketCommandHandler | None = None,
    schema: vol.Schema | None = None,
) -> None:
    """Register a websocket command."""
    # pylint: disable=protected-access
    if handler is None:
        handler = cast(const.WebSocketCommandHandler, command_or_handler)
        command = handler._ws_command  # type: ignore
        schema = handler._ws_schema  # type: ignore
    else:
        command = command_or_handler
    handlers = hass.data.get(DOMAIN)
    if handlers is None:
        handlers = hass.data[DOMAIN] = {}
    handlers[command] = (handler, schema)


async def async_setup(hass, config):
    """Initialize the websocket API."""
    hass.http.register_view(http.WebsocketAPIView)
    commands.async_register_commands(hass, async_register_command)
    return True
