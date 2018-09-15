"""
Websocket based API for Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/developers/websocket_api/
"""
import asyncio
from concurrent import futures
from contextlib import suppress
from functools import partial, wraps
import json
import logging

from aiohttp import web
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.const import (
    MATCH_ALL, EVENT_TIME_CHANGED, EVENT_HOMEASSISTANT_STOP,
    __version__)
from homeassistant.core import Context, callback, HomeAssistant
from homeassistant.loader import bind_hass
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth import validate_password
from homeassistant.components.http.const import KEY_AUTHENTICATED
from homeassistant.components.http.ban import process_wrong_login, \
    process_success_login

DOMAIN = 'websocket_api'

URL = '/api/websocket'
DEPENDENCIES = ('http',)

MAX_PENDING_MSG = 512

ERR_ID_REUSE = 1
ERR_INVALID_FORMAT = 2
ERR_NOT_FOUND = 3
ERR_UNKNOWN_COMMAND = 4

TYPE_AUTH = 'auth'
TYPE_AUTH_INVALID = 'auth_invalid'
TYPE_AUTH_OK = 'auth_ok'
TYPE_AUTH_REQUIRED = 'auth_required'
TYPE_CALL_SERVICE = 'call_service'
TYPE_EVENT = 'event'
TYPE_GET_CONFIG = 'get_config'
TYPE_GET_SERVICES = 'get_services'
TYPE_GET_STATES = 'get_states'
TYPE_PING = 'ping'
TYPE_PONG = 'pong'
TYPE_RESULT = 'result'
TYPE_SUBSCRIBE_EVENTS = 'subscribe_events'
TYPE_UNSUBSCRIBE_EVENTS = 'unsubscribe_events'

_LOGGER = logging.getLogger(__name__)

JSON_DUMP = partial(json.dumps, cls=JSONEncoder)

AUTH_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('type'): TYPE_AUTH,
    vol.Exclusive('api_password', 'auth'): str,
    vol.Exclusive('access_token', 'auth'): str,
})

# Minimal requirements of a message
MINIMAL_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
    vol.Required('type'): cv.string,
}, extra=vol.ALLOW_EXTRA)
# Base schema to extend by message handlers
BASE_COMMAND_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
})


SCHEMA_SUBSCRIBE_EVENTS = BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): TYPE_SUBSCRIBE_EVENTS,
    vol.Optional('event_type', default=MATCH_ALL): str,
})


SCHEMA_UNSUBSCRIBE_EVENTS = BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): TYPE_UNSUBSCRIBE_EVENTS,
    vol.Required('subscription'): cv.positive_int,
})


SCHEMA_CALL_SERVICE = BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): TYPE_CALL_SERVICE,
    vol.Required('domain'): str,
    vol.Required('service'): str,
    vol.Optional('service_data'): dict
})


SCHEMA_GET_STATES = BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): TYPE_GET_STATES,
})


SCHEMA_GET_SERVICES = BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): TYPE_GET_SERVICES,
})


SCHEMA_GET_CONFIG = BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): TYPE_GET_CONFIG,
})


SCHEMA_PING = BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): TYPE_PING,
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


def event_message(iden, event):
    """Return an event message."""
    return {
        'id': iden,
        'type': TYPE_EVENT,
        'event': event.as_dict(),
    }


def error_message(iden, code, message):
    """Return an error result message."""
    return {
        'id': iden,
        'type': TYPE_RESULT,
        'success': False,
        'error': {
            'code': code,
            'message': message,
        },
    }


def pong_message(iden):
    """Return a pong message."""
    return {
        'id': iden,
        'type': TYPE_PONG,
    }


def result_message(iden, result=None):
    """Return a success result message."""
    return {
        'id': iden,
        'type': TYPE_RESULT,
        'success': True,
        'result': result,
    }


@bind_hass
@callback
def async_register_command(hass, command, handler, schema):
    """Register a websocket command."""
    handlers = hass.data.get(DOMAIN)
    if handlers is None:
        handlers = hass.data[DOMAIN] = {}
    handlers[command] = (handler, schema)


def require_owner(func):
    """Websocket decorator to require user to be an owner."""
    @wraps(func)
    def with_owner(hass, connection, msg):
        """Check owner and call function."""
        user = connection.request.get('hass_user')

        if user is None or not user.is_owner:
            connection.to_write.put_nowait(error_message(
                msg['id'], 'unauthorized', 'This command is for owners only.'))
            return

        func(hass, connection, msg)

    return with_owner


async def async_setup(hass, config):
    """Initialize the websocket API."""
    hass.http.register_view(WebsocketAPIView)

    async_register_command(hass, TYPE_SUBSCRIBE_EVENTS,
                           handle_subscribe_events, SCHEMA_SUBSCRIBE_EVENTS)
    async_register_command(hass, TYPE_UNSUBSCRIBE_EVENTS,
                           handle_unsubscribe_events,
                           SCHEMA_UNSUBSCRIBE_EVENTS)
    async_register_command(hass, TYPE_CALL_SERVICE,
                           handle_call_service, SCHEMA_CALL_SERVICE)
    async_register_command(hass, TYPE_GET_STATES,
                           handle_get_states, SCHEMA_GET_STATES)
    async_register_command(hass, TYPE_GET_SERVICES,
                           handle_get_services, SCHEMA_GET_SERVICES)
    async_register_command(hass, TYPE_GET_CONFIG,
                           handle_get_config, SCHEMA_GET_CONFIG)
    async_register_command(hass, TYPE_PING,
                           handle_ping, SCHEMA_PING)

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
                msg = MINIMAL_MESSAGE_SCHEMA(msg)
                cur_id = msg['id']

                if cur_id <= last_id:
                    self.to_write.put_nowait(error_message(
                        cur_id, ERR_ID_REUSE,
                        'Identifier values have to increase.'))

                elif msg['type'] not in handlers:
                    self.log_error(
                        'Received invalid command: {}'.format(msg['type']))
                    self.to_write.put_nowait(error_message(
                        cur_id, ERR_UNKNOWN_COMMAND,
                        'Unknown command.'))

                else:
                    handler, schema = handlers[msg['type']]
                    handler(self.hass, self, schema(msg))

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

                final_message = error_message(
                    iden, ERR_INVALID_FORMAT, error_msg)

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


@callback
def handle_subscribe_events(hass, connection, msg):
    """Handle subscribe events command.

    Async friendly.
    """
    async def forward_events(event):
        """Forward events to websocket."""
        if event.event_type == EVENT_TIME_CHANGED:
            return

        connection.send_message_outside(event_message(msg['id'], event))

    connection.event_listeners[msg['id']] = hass.bus.async_listen(
        msg['event_type'], forward_events)

    connection.to_write.put_nowait(result_message(msg['id']))


@callback
def handle_unsubscribe_events(hass, connection, msg):
    """Handle unsubscribe events command.

    Async friendly.
    """
    subscription = msg['subscription']

    if subscription in connection.event_listeners:
        connection.event_listeners.pop(subscription)()
        connection.to_write.put_nowait(result_message(msg['id']))
    else:
        connection.to_write.put_nowait(error_message(
            msg['id'], ERR_NOT_FOUND, 'Subscription not found.'))


@callback
def handle_call_service(hass, connection, msg):
    """Handle call service command.

    Async friendly.
    """
    async def call_service_helper(msg):
        """Call a service and fire complete message."""
        blocking = True
        if (msg['domain'] == 'homeassistant' and
                msg['service'] in ['restart', 'stop']):
            blocking = False
        await hass.services.async_call(
            msg['domain'], msg['service'], msg.get('service_data'), blocking,
            connection.context(msg))
        connection.send_message_outside(result_message(msg['id']))

    hass.async_add_job(call_service_helper(msg))


@callback
def handle_get_states(hass, connection, msg):
    """Handle get states command.

    Async friendly.
    """
    connection.to_write.put_nowait(result_message(
        msg['id'], hass.states.async_all()))


@callback
def handle_get_services(hass, connection, msg):
    """Handle get services command.

    Async friendly.
    """
    async def get_services_helper(msg):
        """Get available services and fire complete message."""
        descriptions = await async_get_all_descriptions(hass)
        connection.send_message_outside(
            result_message(msg['id'], descriptions))

    hass.async_add_job(get_services_helper(msg))


@callback
def handle_get_config(hass, connection, msg):
    """Handle get config command.

    Async friendly.
    """
    connection.to_write.put_nowait(result_message(
        msg['id'], hass.config.as_dict()))


@callback
def handle_ping(hass, connection, msg):
    """Handle ping command.

    Async friendly.
    """
    connection.to_write.put_nowait(pong_message(msg['id']))


def ws_require_user(
        only_owner=False, only_system_user=False, allow_system_user=True,
        only_active_user=True, only_inactive_user=False):
    """Decorate function validating login user exist in current WS connection.

    Will write out error message if not authenticated.
    """
    def validator(func):
        """Decorate func."""
        @wraps(func)
        def check_current_user(hass: HomeAssistant,
                               connection: ActiveConnection,
                               msg):
            """Check current user."""
            def output_error(message_id, message):
                """Output error message."""
                connection.send_message_outside(error_message(
                    msg['id'], message_id, message))

            if connection.user is None:
                output_error('no_user', 'Not authenticated as a user')
                return

            if only_owner and not connection.user.is_owner:
                output_error('only_owner', 'Only allowed as owner')
                return

            if (only_system_user and
                    not connection.user.system_generated):
                output_error('only_system_user',
                             'Only allowed as system user')
                return

            if (not allow_system_user
                    and connection.user.system_generated):
                output_error('not_system_user', 'Not allowed as system user')
                return

            if (only_active_user and
                    not connection.user.is_active):
                output_error('only_active_user',
                             'Only allowed as active user')
                return

            if only_inactive_user and connection.user.is_active:
                output_error('only_inactive_user',
                             'Not allowed as active user')
                return

            return func(hass, connection, msg)

        return check_current_user

    return validator
