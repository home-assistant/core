"""Websocket based API for Home Assistant."""
import asyncio
from functools import partial
import json
import logging

import aiohttp
from aiohttp import web
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.const import (
    MATCH_ALL, EVENT_TIME_CHANGED, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
from homeassistant.remote import JSONEncoder
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth import validate_password
from homeassistant.components.http.const import KEY_AUTHENTICATED

DOMAIN = 'websocket_api'

URL = "/api/websocket"
DEPENDENCIES = 'http',

ERR_INVALID_JSON = 1
ERR_INVALID_AUTH = 2
ERR_INVALID_FORMAT = 3
ERR_INVALID_MSG_TYPE = 4
ERR_AUTH_REQUIRED = 5

TYPE_ERROR = 'error'
TYPE_AUTH = 'auth'
TYPE_AUTH_OK = 'auth_ok'
TYPE_AUTH_REQUIRED = 'auth_required'
TYPE_EVENT = 'event'
TYPE_LISTEN_EVENT = 'listen_event'
TYPE_CALL_SERVICE = 'call_service'

_LOGGER = logging.getLogger(__name__)

JSON_DUMP = partial(json.dumps, cls=JSONEncoder)

AUTH_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('type'): TYPE_AUTH,
    vol.Required('api_password'): str,
})

LISTEN_EVENT_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('type'): TYPE_LISTEN_EVENT,
    vol.Optional('event_type', default=MATCH_ALL): str,
})

CALL_SERVICE_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('type'): TYPE_CALL_SERVICE,
    vol.Required('domain'): str,
    vol.Required('service'): str,
    vol.Optional('service_data', default=None): dict
})

SERVER_MESSAGE_SCHEMA = vol.Any(LISTEN_EVENT_MESSAGE_SCHEMA,
                                CALL_SERVICE_MESSAGE_SCHEMA)


def auth_ok_message():
    """Return an auth_ok message."""
    return {
        'type': TYPE_AUTH_OK
    }


def auth_required_message():
    """Return an auth_ok message."""
    return {
        'type': TYPE_AUTH_REQUIRED
    }


def event_message(event):
    """Return an event message."""
    return {
        'type': TYPE_EVENT,
        'event': event.as_dict(),
    }


def error_message(code, message):
    """Return an error message."""
    return {
        'type': TYPE_ERROR,
        'error': {
            'code': code,
            'message': message,
        },
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

        def error(message1, message2=''):
            """Print an error message."""
            _LOGGER.error('WS %s: %s %s', id(wsock), message1, message2)

        disconnect_tasks = []

        debug('Connected')

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

        @callback
        def forward_event(event):
            """Event listener that forwards events to websocket."""
            if event.event_type == EVENT_TIME_CHANGED:
                return

            send_message(event_message(event))

        msg = None
        authenticated = False

        try:
            # Validate authentication
            if request[KEY_AUTHENTICATED]:
                send_message(auth_ok_message())
                authenticated = True

            else:
                send_message(auth_required_message())
                msg = yield from wsock.receive_json()
                msg = AUTH_MESSAGE_SCHEMA(msg)

                if not validate_password(request, msg['api_password']):
                    debug('Invalid password')
                    send_message(error_message(ERR_INVALID_AUTH,
                                               'Invalid password'))
                    return wsock

                authenticated = True
                send_message(auth_ok_message())

            msg = yield from wsock.receive_json()

            while msg:
                debug('Received', msg)
                msg = SERVER_MESSAGE_SCHEMA(msg)

                if msg['type'] == TYPE_LISTEN_EVENT:
                    disconnect_tasks.append(
                        hass.bus.async_listen(msg['event_type'],
                                              forward_event))

                elif msg['type'] == TYPE_CALL_SERVICE:
                    hass.async_add_job(hass.services.async_call, msg['domain'],
                                       msg['service'], msg['service_data'])

                msg = yield from wsock.receive_json()

        except vol.Invalid as err:
            # When we require authentication, the first message has to be
            # of type='auth'. If it wasn't, give a more helpful error message.
            if (not authenticated and isinstance(msg, dict) and
                    msg.get('type') != TYPE_AUTH):
                error_code = ERR_AUTH_REQUIRED
                error_msg = 'Authentication required'
            else:
                error_code = ERR_INVALID_FORMAT
                error_msg = 'Message incorrectly formatted: '
                if msg:
                    error_msg += humanize_error(msg, err)
                else:
                    error_msg += str(err)

            error(error_msg)
            send_message(error_message(error_code, error_msg))

        except TypeError as err:
            # We did not get a string message
            msg = yield from wsock.receive()

            if msg.type == aiohttp.WSMsgType.CLOSED:
                debug('Connection closed by client')
            else:
                error('Received unexpected message from client', msg)

        except ValueError as err:
            # String message contained invalid JSON
            msg = 'Received invalid JSON'
            value = getattr(err, 'doc', None)  # Py3.5+ only
            if value:
                msg += ': {}'.format(value)

            error(msg)
            send_message(error_message(ERR_INVALID_FORMAT, msg))

        except asyncio.CancelledError:
            debug('Connection cancelled by server')

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Unexpected error inside websocket API.')

        finally:
            for task in disconnect_tasks:
                task()

            yield from wsock.close()
            debug('Closed connection')

        return wsock
