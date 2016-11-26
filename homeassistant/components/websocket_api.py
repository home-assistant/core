"""Websocket based API for Home Assistant."""
import asyncio
from functools import partial
import json
import logging

from aiohttp import web
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.const import (
    MATCH_ALL, EVENT_TIME_CHANGED, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
from homeassistant.remote import JSONEncoder
from homeassistant.helpers import config_validation as cv
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth import validate_password
from homeassistant.components.http.const import KEY_AUTHENTICATED

DOMAIN = 'websocket_api'

URL = "/api/websocket"
DEPENDENCIES = 'http',

ERR_ID_REUSE = 1
ERR_INVALID_FORMAT = 2

TYPE_AUTH = 'auth'
TYPE_AUTH_OK = 'auth_ok'
TYPE_AUTH_REQUIRED = 'auth_required'
TYPE_AUTH_INVALID = 'auth_invalid'
TYPE_EVENT = 'event'
TYPE_LISTEN_EVENT = 'listen_event'
TYPE_CALL_SERVICE = 'call_service'
TYPE_RESULT = 'result'

_LOGGER = logging.getLogger(__name__)

JSON_DUMP = partial(json.dumps, cls=JSONEncoder)

AUTH_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('type'): TYPE_AUTH,
    vol.Required('api_password'): str,
})

LISTEN_EVENT_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
    vol.Required('type'): TYPE_LISTEN_EVENT,
    vol.Optional('event_type', default=MATCH_ALL): str,
})

CALL_SERVICE_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
    vol.Required('type'): TYPE_CALL_SERVICE,
    vol.Required('domain'): str,
    vol.Required('service'): str,
    vol.Optional('service_data', default=None): dict
})

SERVER_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): cv.positive_int,
    vol.Required('type'): vol.Any(TYPE_CALL_SERVICE, TYPE_LISTEN_EVENT)
}, extra=vol.ALLOW_EXTRA)


def auth_ok_message():
    """Return an auth_ok message."""
    return {
        'type': TYPE_AUTH_OK
    }


def auth_required_message():
    """Return an auth_required message."""
    return {
        'type': TYPE_AUTH_REQUIRED
    }


def auth_invalid_message(message):
    """Return an auth_invalid message."""
    return {
        'type': TYPE_AUTH_INVALID,
        'message': message
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
        hass = request.app['hass']
        wsock = web.WebSocketResponse()
        yield from wsock.prepare(request)

        def debug(message1, message2=''):
            """Print a debug message."""
            _LOGGER.debug('WS %s: %s %s', id(wsock), message1, message2)

        def log_error(message1, message2=''):
            """Print an error message."""
            _LOGGER.error('WS %s: %s %s', id(wsock), message1, message2)

        # Set up to cancel this connection when Home Assistant shuts down
        socket_task = asyncio.Task.current_task(loop=hass.loop)

        @callback
        def cancel_connection(event):
            """Cancel this connection."""
            socket_task.cancel()

        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, cancel_connection)

        def send_message(message):
            """Helper method to send messages."""
            debug('Sending', message)
            wsock.send_json(message, dumps=JSON_DUMP)

        debug('Connected')

        msg = None
        authenticated = False
        event_listeners = {}

        try:
            if request[KEY_AUTHENTICATED]:
                authenticated = True

            else:
                send_message(auth_required_message())
                msg = yield from wsock.receive_json()
                msg = AUTH_MESSAGE_SCHEMA(msg)

                if validate_password(request, msg['api_password']):
                    authenticated = True

                else:
                    debug('Invalid password')
                    send_message(auth_invalid_message('Invalid password'))
                    return wsock

            if not authenticated:
                return wsock

            send_message(auth_ok_message())

            msg = yield from wsock.receive_json()

            last_id = 0

            while msg:
                debug('Received', msg)
                msg = SERVER_MESSAGE_SCHEMA(msg)
                cur_id = msg['id']

                if cur_id < last_id:
                    send_message(error_message(
                        cur_id, ERR_ID_REUSE,
                        'Identifier values have to increase.'))

                elif msg['type'] == TYPE_LISTEN_EVENT:
                    msg = LISTEN_EVENT_MESSAGE_SCHEMA(msg)

                    event_listeners[msg['id']] = hass.bus.async_listen(
                        msg['event_type'],
                        partial(_forward_event, msg['id'], send_message))

                    send_message(result_message(msg['id']))

                elif msg['type'] == TYPE_CALL_SERVICE:
                    msg = CALL_SERVICE_MESSAGE_SCHEMA(msg)

                    hass.async_add_job(_call_service_helper(hass, msg,
                                                            send_message))

                last_id = cur_id
                msg = yield from wsock.receive_json()

        except vol.Invalid as err:
            error_msg = 'Message incorrectly formatted: '
            if msg:
                error_msg += humanize_error(msg, err)
            else:
                error_msg += str(err)

            log_error(error_msg)

            if not authenticated:
                send_message(auth_invalid_message(error_msg))

            else:
                if isinstance(msg, dict):
                    iden = msg.get('id')
                else:
                    iden = None

                send_message(error_message(iden, ERR_INVALID_FORMAT,
                                           error_msg))

        except TypeError as err:
            if wsock.closed:
                debug('Connection closed by client')
            else:
                log_error('Unexpected TypeError', msg)

        except ValueError as err:
            msg = 'Received invalid JSON'
            value = getattr(err, 'doc', None)  # Py3.5+ only
            if value:
                msg += ': {}'.format(value)
            log_error(msg)

        except asyncio.CancelledError:
            debug('Connection cancelled by server')

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Unexpected error inside websocket API.')

        finally:
            for unsub in event_listeners.values():
                unsub()

            yield from wsock.close()
            debug('Closed connection')

        return wsock


@asyncio.coroutine
def _call_service_helper(hass, msg, send_message):
    """Helper to call a service and fire complete message."""
    yield from hass.services.async_call(msg['domain'], msg['service'],
                                        msg['service_data'])
    try:
        send_message(result_message(msg['id']))
    except RuntimeError:
        # Socket has been closed.
        pass


@callback
def _forward_event(iden, send_message, event):
    """Helper to forward events to websocket."""
    if event.event_type == EVENT_TIME_CHANGED:
        return

    try:
        send_message(event_message(iden, event))
    except RuntimeError:
        # Socket has been closed.
        pass
