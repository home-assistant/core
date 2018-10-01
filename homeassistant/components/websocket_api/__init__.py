"""
Websocket based API for Home Assistant.

For more details about this component, please refer to the documentation at
https://developers.home-assistant.io/docs/external_api_websocket.html
"""
import asyncio
from concurrent import futures
from contextlib import suppress
from functools import partial
import json
import logging

from aiohttp import web
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, __version__
from homeassistant.core import Context, callback
from homeassistant.loader import bind_hass
from homeassistant.helpers.json import JSONEncoder
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth import validate_password
from homeassistant.components.http.const import KEY_AUTHENTICATED
from homeassistant.components.http.ban import process_wrong_login, \
    process_success_login

from . import commands, const, decorators, messages

DOMAIN = 'websocket_api'

URL = '/api/websocket'
DEPENDENCIES = ('http',)

MAX_PENDING_MSG = 512


_LOGGER = logging.getLogger(__name__)

JSON_DUMP = partial(json.dumps, cls=JSONEncoder)

TYPE_AUTH = 'auth'
TYPE_AUTH_INVALID = 'auth_invalid'
TYPE_AUTH_OK = 'auth_ok'
TYPE_AUTH_REQUIRED = 'auth_required'


# Backwards compat
# pylint: disable=invalid-name
BASE_COMMAND_MESSAGE_SCHEMA = messages.BASE_COMMAND_MESSAGE_SCHEMA
error_message = messages.error_message
result_message = messages.result_message
async_response = decorators.async_response
ws_require_user = decorators.ws_require_user
# pylint: enable=invalid-name

AUTH_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('type'): TYPE_AUTH,
    vol.Exclusive('api_password', 'auth'): str,
    vol.Exclusive('access_token', 'auth'): str,
})


# Define the possible errors that occur when connections are cancelled.
# Originally, this was just asyncio.CancelledError, but issue #9546 showed
# that futures.CancelledErrors can also occur in some situations.
CANCELLATION_ERRORS = (asyncio.CancelledError, futures.CancelledError)


def auth_ok_message():
    """Return an auth_ok message."""
    return {
        'type': TYPE_AUTH_OK,
        'ha_version': __version__,
    }


def auth_required_message():
    """Return an auth_required message."""
    return {
        'type': TYPE_AUTH_REQUIRED,
        'ha_version': __version__,
    }


def auth_invalid_message(message):
    """Return an auth_invalid message."""
    return {
        'type': TYPE_AUTH_INVALID,
        'message': message,
    }


@bind_hass
@callback
def async_register_command(hass, command, handler, schema):
    """Register a websocket command."""
    handlers = hass.data.get(DOMAIN)
    if handlers is None:
        handlers = hass.data[DOMAIN] = {}
    handlers[command] = (handler, schema)


async def async_setup(hass, config):
    """Initialize the websocket API."""
    hass.http.register_view(WebsocketAPIView)
    commands.async_register_commands(hass)
    return True


class WebsocketAPIView(HomeAssistantView):
    """View to serve a websockets endpoint."""

    name = "websocketapi"
    url = URL
    requires_auth = False

    async def get(self, request):
        """Handle an incoming websocket connection."""
        return await ActiveConnection(request.app['hass'], request).handle()


class ActiveConnection:
    """Handle an active websocket client connection."""

    def __init__(self, hass, request):
        """Initialize an active connection."""
        self.hass = hass
        self.request = request
        self.wsock = None
        self.event_listeners = {}
        self.to_write = asyncio.Queue(maxsize=MAX_PENDING_MSG, loop=hass.loop)
        self._handle_task = None
        self._writer_task = None

    @property
    def user(self):
        """Return the user associated with the connection."""
        return self.request.get('hass_user')

    def context(self, msg):
        """Return a context."""
        user = self.user
        if user is None:
            return Context()
        return Context(user_id=user.id)

    def debug(self, message1, message2=''):
        """Print a debug message."""
        _LOGGER.debug("WS %s: %s %s", id(self.wsock), message1, message2)

    def log_error(self, message1, message2=''):
        """Print an error message."""
        _LOGGER.error("WS %s: %s %s", id(self.wsock), message1, message2)

    async def _writer(self):
        """Write outgoing messages."""
        # Exceptions if Socket disconnected or cancelled by connection handler
        with suppress(RuntimeError, *CANCELLATION_ERRORS):
            while not self.wsock.closed:
                message = await self.to_write.get()
                if message is None:
                    break
                self.debug("Sending", message)
                try:
                    await self.wsock.send_json(message, dumps=JSON_DUMP)
                except TypeError as err:
                    _LOGGER.error('Unable to serialize to JSON: %s\n%s',
                                  err, message)

    @callback
    def send_message_outside(self, message):
        """Send a message to the client.

        Closes connection if the client is not reading the messages.

        Async friendly.
        """
        try:
            self.to_write.put_nowait(message)
        except asyncio.QueueFull:
            self.log_error("Client exceeded max pending messages [2]:",
                           MAX_PENDING_MSG)
            self.cancel()

    @callback
    def cancel(self):
        """Cancel the connection."""
        self._handle_task.cancel()
        self._writer_task.cancel()

    async def handle(self):
        """Handle the websocket connection."""
        request = self.request
        wsock = self.wsock = web.WebSocketResponse(heartbeat=55)
        await wsock.prepare(request)
        self.debug("Connected")

        self._handle_task = asyncio.Task.current_task(loop=self.hass.loop)

        @callback
        def handle_hass_stop(event):
            """Cancel this connection."""
            self.cancel()

        unsub_stop = self.hass.bus.async_listen(
            EVENT_HOMEASSISTANT_STOP, handle_hass_stop)
        self._writer_task = self.hass.async_add_job(self._writer())
        final_message = None
        msg = None
        authenticated = False

        try:
            if request[KEY_AUTHENTICATED]:
                authenticated = True

            # always request auth when auth is active
            #   even request passed pre-authentication (trusted networks)
            # or when using legacy api_password
            if self.hass.auth.active or not authenticated:
                self.debug("Request auth")
                await self.wsock.send_json(auth_required_message())
                msg = await wsock.receive_json()
                msg = AUTH_MESSAGE_SCHEMA(msg)

                if self.hass.auth.active and 'access_token' in msg:
                    self.debug("Received access_token")
                    refresh_token = \
                        await self.hass.auth.async_validate_access_token(
                            msg['access_token'])
                    authenticated = refresh_token is not None
                    if authenticated:
                        request['hass_user'] = refresh_token.user
                        request['refresh_token_id'] = refresh_token.id

                elif ((not self.hass.auth.active or
                       self.hass.auth.support_legacy) and
                      'api_password' in msg):
                    self.debug("Received api_password")
                    authenticated = validate_password(
                        request, msg['api_password'])

            if not authenticated:
                self.debug("Authorization failed")
                await self.wsock.send_json(
                    auth_invalid_message('Invalid access token or password'))
                await process_wrong_login(request)
                return wsock

            self.debug("Auth OK")
            await process_success_login(request)
            await self.wsock.send_json(auth_ok_message())

            # ---------- AUTH PHASE OVER ----------

            msg = await wsock.receive_json()
            last_id = 0
            handlers = self.hass.data[DOMAIN]

            while msg:
                self.debug("Received", msg)
                msg = messages.MINIMAL_MESSAGE_SCHEMA(msg)
                cur_id = msg['id']

                if cur_id <= last_id:
                    self.to_write.put_nowait(messages.error_message(
                        cur_id, const.ERR_ID_REUSE,
                        'Identifier values have to increase.'))

                elif msg['type'] not in handlers:
                    self.log_error(
                        'Received invalid command: {}'.format(msg['type']))
                    self.to_write.put_nowait(messages.error_message(
                        cur_id, const.ERR_UNKNOWN_COMMAND,
                        'Unknown command.'))

                else:
                    handler, schema = handlers[msg['type']]
                    try:
                        handler(self.hass, self, schema(msg))
                    except Exception:  # pylint: disable=broad-except
                        _LOGGER.exception('Error handling message: %s', msg)
                        self.to_write.put_nowait(messages.error_message(
                            cur_id, const.ERR_UNKNOWN_ERROR,
                            'Unknown error.'))

                last_id = cur_id
                msg = await wsock.receive_json()

        except vol.Invalid as err:
            error_msg = "Message incorrectly formatted: "
            if msg:
                error_msg += humanize_error(msg, err)
            else:
                error_msg += str(err)

            self.log_error(error_msg)

            if not authenticated:
                final_message = auth_invalid_message(error_msg)

            else:
                if isinstance(msg, dict):
                    iden = msg.get('id')
                else:
                    iden = None

                final_message = messages.error_message(
                    iden, const.ERR_INVALID_FORMAT, error_msg)

        except TypeError as err:
            if wsock.closed:
                self.debug("Connection closed by client")
            else:
                _LOGGER.exception("Unexpected TypeError: %s", err)

        except ValueError as err:
            msg = "Received invalid JSON"
            value = getattr(err, 'doc', None)  # Py3.5+ only
            if value:
                msg += ': {}'.format(value)
            self.log_error(msg)
            self._writer_task.cancel()

        except CANCELLATION_ERRORS:
            self.debug("Connection cancelled")

        except asyncio.QueueFull:
            self.log_error("Client exceeded max pending messages [1]:",
                           MAX_PENDING_MSG)
            self._writer_task.cancel()

        except Exception:  # pylint: disable=broad-except
            error = "Unexpected error inside websocket API. "
            if msg is not None:
                error += str(msg)
            _LOGGER.exception(error)

        finally:
            unsub_stop()

            for unsub in self.event_listeners.values():
                unsub()

            try:
                if final_message is not None:
                    self.to_write.put_nowait(final_message)
                self.to_write.put_nowait(None)
                # Make sure all error messages are written before closing
                await self._writer_task
            except asyncio.QueueFull:
                self._writer_task.cancel()

            await wsock.close()
            self.debug("Closed connection")

        return wsock
