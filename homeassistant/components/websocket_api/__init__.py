"""WebSocket based API for Home Assistant."""
from homeassistant.core import callback
from homeassistant.loader import bind_hass

from . import commands, connection, const, decorators, http, messages

DOMAIN = const.DOMAIN

DEPENDENCIES = ('http',)

# Backwards compat / Make it easier to integrate
# pylint: disable=invalid-name
ActiveConnection = connection.ActiveConnection
BASE_COMMAND_MESSAGE_SCHEMA = messages.BASE_COMMAND_MESSAGE_SCHEMA
error_message = messages.error_message
result_message = messages.result_message
event_message = messages.event_message
async_response = decorators.async_response
require_admin = decorators.require_admin
ws_require_user = decorators.ws_require_user
websocket_command = decorators.websocket_command
# pylint: enable=invalid-name


@bind_hass
@callback
def async_register_command(hass, command_or_handler, handler=None,
                           schema=None):
    """Register a websocket command."""
    # pylint: disable=protected-access
    if handler is None:
        handler = command_or_handler
        command = handler._ws_command
        schema = handler._ws_schema
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
