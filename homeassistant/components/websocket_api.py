"""Websocket based API for Home Assistant."""
import asyncio
from functools import partial
import json
import logging

from aiohttp import web
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.const import (
    MATCH_ALL, EVENT_TIME_CHANGED, EVENT_HOMEASSISTANT_STOP,
    __version__)
from homeassistant.components import frontend
from homeassistant.core import callback
from homeassistant.remote import JSONEncoder
from homeassistant.helpers import config_validation as cv
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth import validate_password
from homeassistant.components.http.const import KEY_AUTHENTICATED
from homeassistant.components.http.ban import process_wrong_login

DOMAIN = 'websocket_api'

URL = "/api/websocket"
DEPENDENCIES = 'http',

ERR_ID_REUSE = 1
ERR_INVALID_FORMAT = 2
ERR_NOT_FOUND = 3

TYPE_AUTH = 'auth'
TYPE_AUTH_INVALID = 'auth_invalid'
TYPE_AUTH_OK = 'auth_ok'
TYPE_AUTH_REQUIRED = 'auth_required'
TYPE_CALL_SERVICE = 'call_service'
TYPE_EVENT = 'event'
TYPE_GET_CONFIG = 'get_config'
TYPE_GET_PANELS = 'get_panels'
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
    vol.Required('api_password'): str,
})

SUBSCRIBE_EVENTS_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
    vol.Required('type'): TYPE_SUBSCRIBE_EVENTS,
    vol.Optional('event_type', default=MATCH_ALL): str,
})

UNSUBSCRIBE_EVENTS_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
    vol.Required('type'): TYPE_UNSUBSCRIBE_EVENTS,
    vol.Required('subscription'): cv.positive_int,
})

CALL_SERVICE_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
    vol.Required('type'): TYPE_CALL_SERVICE,
    vol.Required('domain'): str,
    vol.Required('service'): str,
    vol.Optional('service_data', default=None): dict
})

GET_STATES_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
    vol.Required('type'): TYPE_GET_STATES,
})

GET_SERVICES_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
    vol.Required('type'): TYPE_GET_SERVICES,
})

GET_CONFIG_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
    vol.Required('type'): TYPE_GET_CONFIG,
})

GET_PANELS_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
    vol.Required('type'): TYPE_GET_PANELS,
})

PING_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
    vol.Required('type'): TYPE_PING,
})

BASE_COMMAND_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
    vol.Required('type'): vol.Any(TYPE_CALL_SERVICE,
                                  TYPE_SUBSCRIBE_EVENTS,
                                  TYPE_UNSUBSCRIBE_EVENTS,
                                  TYPE_GET_STATES,
                                  TYPE_GET_SERVICES,
                                  TYPE_GET_CONFIG,
                                  TYPE_GET_PANELS,
                                  TYPE_PING)
}, extra=vol.ALLOW_EXTRA)


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


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the websocket API."""
    hass.http.register_view(WebsocketAPIView)
    return True


class WebsocketAPIView(HomeAssistantView):
    """View to serve a websockets endpoint."""

    name = "websocketapi"
    url = URL
    requires_auth = False

    @asyncio.coroutine
    def get(self, request):
        """Handle an incoming websocket connection."""
        # pylint: disable=no-self-use
        return ActiveConnection(request.app['hass'], request).handle()


class ActiveConnection:
    """Handle an active websocket client connection."""

    def __init__(self, hass, request):
        """Initialize an active connection."""
        self.hass = hass
        self.request = request
        self.wsock = None
        self.event_listeners = {}

    def debug(self, message1, message2=''):
        """Print a debug message."""
        _LOGGER.debug('WS %s: %s %s', id(self.wsock), message1, message2)

    def log_error(self, message1, message2=''):
        """Print an error message."""
        _LOGGER.error('WS %s: %s %s', id(self.wsock), message1, message2)

    def send_message(self, message):
        """Helper method to send messages."""
        self.debug('Sending', message)
        self.wsock.send_json(message, dumps=JSON_DUMP)

    @asyncio.coroutine
    def handle(self):
        """Handle the websocket connection."""
        wsock = self.wsock = web.WebSocketResponse()
        yield from wsock.prepare(self.request)

        # Set up to cancel this connection when Home Assistant shuts down
        socket_task = asyncio.Task.current_task(loop=self.hass.loop)

        @callback
        def cancel_connection(event):
            """Cancel this connection."""
            socket_task.cancel()

        unsub_stop = self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP,
                                                cancel_connection)

        self.debug('Connected')

        msg = None
        authenticated = False

        try:
            if self.request[KEY_AUTHENTICATED]:
                authenticated = True

            else:
                self.send_message(auth_required_message())
                msg = yield from wsock.receive_json()
                msg = AUTH_MESSAGE_SCHEMA(msg)

                if validate_password(self.request, msg['api_password']):
                    authenticated = True

                else:
                    self.debug('Invalid password')
                    self.send_message(auth_invalid_message('Invalid password'))

            if not authenticated:
                yield from process_wrong_login(self.request)
                return wsock

            self.send_message(auth_ok_message())

            msg = yield from wsock.receive_json()

            last_id = 0

            while msg:
                self.debug('Received', msg)
                msg = BASE_COMMAND_MESSAGE_SCHEMA(msg)
                cur_id = msg['id']

                if cur_id <= last_id:
                    self.send_message(error_message(
                        cur_id, ERR_ID_REUSE,
                        'Identifier values have to increase.'))

                else:
                    handler_name = 'handle_{}'.format(msg['type'])
                    getattr(self, handler_name)(msg)

                last_id = cur_id
                msg = yield from wsock.receive_json()

        except vol.Invalid as err:
            error_msg = 'Message incorrectly formatted: '
            if msg:
                error_msg += humanize_error(msg, err)
            else:
                error_msg += str(err)

            self.log_error(error_msg)

            if not authenticated:
                self.send_message(auth_invalid_message(error_msg))

            else:
                if isinstance(msg, dict):
                    iden = msg.get('id')
                else:
                    iden = None

                self.send_message(error_message(iden, ERR_INVALID_FORMAT,
                                                error_msg))

        except TypeError as err:
            if wsock.closed:
                self.debug('Connection closed by client')
            else:
                self.log_error('Unexpected TypeError', msg)

        except ValueError as err:
            msg = 'Received invalid JSON'
            value = getattr(err, 'doc', None)  # Py3.5+ only
            if value:
                msg += ': {}'.format(value)
            self.log_error(msg)

        except asyncio.CancelledError:
            self.debug('Connection cancelled by server')

        except Exception:  # pylint: disable=broad-except
            error = 'Unexpected error inside websocket API. '
            if msg is not None:
                error += str(msg)
            _LOGGER.exception(error)

        finally:
            unsub_stop()

            for unsub in self.event_listeners.values():
                unsub()

            yield from wsock.close()
            self.debug('Closed connection')

        return wsock

    def handle_subscribe_events(self, msg):
        """Handle subscribe events command."""
        msg = SUBSCRIBE_EVENTS_MESSAGE_SCHEMA(msg)

        @callback
        def forward_events(event):
            """Helper to forward events to websocket."""
            if event.event_type == EVENT_TIME_CHANGED:
                return

            try:
                self.send_message(event_message(msg['id'], event))
            except RuntimeError:
                # Socket has been closed.
                pass

        self.event_listeners[msg['id']] = self.hass.bus.async_listen(
            msg['event_type'], forward_events)

        self.send_message(result_message(msg['id']))

    def handle_unsubscribe_events(self, msg):
        """Handle unsubscribe events command."""
        msg = UNSUBSCRIBE_EVENTS_MESSAGE_SCHEMA(msg)

        subscription = msg['subscription']

        if subscription not in self.event_listeners:
            self.send_message(error_message(
                msg['id'], ERR_NOT_FOUND,
                'Subscription not found.'))
        else:
            self.event_listeners.pop(subscription)()
            self.send_message(result_message(msg['id']))

    def handle_call_service(self, msg):
        """Handle call service command."""
        msg = CALL_SERVICE_MESSAGE_SCHEMA(msg)

        @asyncio.coroutine
        def call_service_helper(msg):
            """Helper to call a service and fire complete message."""
            yield from self.hass.services.async_call(
                msg['domain'], msg['service'], msg['service_data'], True)
            try:
                self.send_message(result_message(msg['id']))
            except RuntimeError:
                # Socket has been closed.
                pass

        self.hass.async_add_job(call_service_helper(msg))

    def handle_get_states(self, msg):
        """Handle get states command."""
        msg = GET_STATES_MESSAGE_SCHEMA(msg)

        self.send_message(result_message(msg['id'],
                                         self.hass.states.async_all()))

    def handle_get_services(self, msg):
        """Handle get services command."""
        msg = GET_SERVICES_MESSAGE_SCHEMA(msg)

        self.send_message(result_message(msg['id'],
                                         self.hass.services.async_services()))

    def handle_get_config(self, msg):
        """Handle get config command."""
        msg = GET_CONFIG_MESSAGE_SCHEMA(msg)

        self.send_message(result_message(msg['id'],
                                         self.hass.config.as_dict()))

    def handle_get_panels(self, msg):
        """Handle get panels command."""
        msg = GET_PANELS_MESSAGE_SCHEMA(msg)

        self.send_message(result_message(
            msg['id'], self.hass.data[frontend.DATA_PANELS]))

    def handle_ping(self, msg):
        """Handle ping command."""
        self.send_message(pong_message(msg['id']))
