"""WebSocket based API for Home Assistant."""
from typing import Optional, Union, cast

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import bind_hass

from . import commands, connection, const, decorators, http, messages  # noqa
from .connection import ActiveConnection  # noqa
from .const import (  # noqa
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
from .decorators import (  # noqa
    async_response,
    require_admin,
    websocket_command,
    ws_require_user,
)
from .messages import (  # noqa
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
    command_or_handler: Union[str, const.WebSocketCommandHandler],
    handler: Optional[const.WebSocketCommandHandler] = None,
    schema: Optional[vol.Schema] = None,
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
