"""Module to handle messages from Home Assistant cloud."""
import asyncio
import logging
import pprint

from aiohttp import hdrs, client_exceptions, WSMsgType

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.components.alexa import smart_home as alexa
from homeassistant.components.google_assistant import smart_home as ga
from homeassistant.util.decorator import Registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from . import auth_api
from .const import MESSAGE_EXPIRATION, MESSAGE_AUTH_FAIL

HANDLERS = Registry()
_LOGGER = logging.getLogger(__name__)

STATE_CONNECTING = 'connecting'
STATE_CONNECTED = 'connected'
STATE_DISCONNECTED = 'disconnected'


class UnknownHandler(Exception):
    """Exception raised when trying to handle unknown handler."""


class CloudIoT:
    """Class to manage the IoT connection."""

    def __init__(self, cloud):
        """Initialize the CloudIoT class."""
        self.cloud = cloud
        # The WebSocket client
        self.client = None
        # Scheduled sleep task till next connection retry
        self.retry_task = None
        # Boolean to indicate if we wanted the connection to close
        self.close_requested = False
        # The current number of attempts to connect, impacts wait time
        self.tries = 0
        # Current state of the connection
        self.state = STATE_DISCONNECTED

    @asyncio.coroutine
    def connect(self):
        """Connect to the IoT broker."""
        if self.state != STATE_DISCONNECTED:
            raise RuntimeError('Connect called while not disconnected')

        hass = self.cloud.hass
        self.close_requested = False
        self.state = STATE_CONNECTING
        self.tries = 0

        @asyncio.coroutine
        def _handle_hass_stop(event):
            """Handle Home Assistant shutting down."""
            nonlocal remove_hass_stop_listener
            remove_hass_stop_listener = None
            yield from self.disconnect()

        remove_hass_stop_listener = hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, _handle_hass_stop)

        while True:
            try:
                yield from self._handle_connection()
            except Exception:  # pylint: disable=broad-except
                # Safety net. This should never hit.
                # Still adding it here to make sure we can always reconnect
                _LOGGER.exception("Unexpected error")

            if self.close_requested:
                break

            self.state = STATE_CONNECTING
            self.tries += 1

            try:
                # Sleep 2^tries seconds between retries
                self.retry_task = hass.async_add_job(asyncio.sleep(
                    2**min(9, self.tries), loop=hass.loop))
                yield from self.retry_task
                self.retry_task = None
            except asyncio.CancelledError:
                # Happens if disconnect called
                break

        self.state = STATE_DISCONNECTED
        if remove_hass_stop_listener is not None:
            remove_hass_stop_listener()

    @asyncio.coroutine
    def _handle_connection(self):
        """Connect to the IoT broker."""
        hass = self.cloud.hass

        try:
            yield from hass.async_add_job(auth_api.check_token, self.cloud)
        except auth_api.Unauthenticated as err:
            _LOGGER.error('Unable to refresh token: %s', err)

            hass.components.persistent_notification.async_create(
                MESSAGE_AUTH_FAIL, 'Home Assistant Cloud',
                'cloud_subscription_expired')

            # Don't await it because it will cancel this task
            hass.async_add_job(self.cloud.logout())
            return
        except auth_api.CloudError as err:
            _LOGGER.warning("Unable to refresh token: %s", err)
            return

        if self.cloud.subscription_expired:
            hass.components.persistent_notification.async_create(
                MESSAGE_EXPIRATION, 'Home Assistant Cloud',
                'cloud_subscription_expired')
            self.close_requested = True
            return

        session = async_get_clientsession(self.cloud.hass)
        client = None
        disconnect_warn = None

        try:
            self.client = client = yield from session.ws_connect(
                self.cloud.relayer, heartbeat=55, headers={
                    hdrs.AUTHORIZATION:
                        'Bearer {}'.format(self.cloud.id_token)
                })
            self.tries = 0

            _LOGGER.info("Connected")
            self.state = STATE_CONNECTED

            while not client.closed:
                msg = yield from client.receive()

                if msg.type in (WSMsgType.CLOSED, WSMsgType.CLOSING):
                    break

                elif msg.type == WSMsgType.ERROR:
                    disconnect_warn = 'Connection error'
                    break

                elif msg.type != WSMsgType.TEXT:
                    disconnect_warn = 'Received non-Text message: {}'.format(
                        msg.type)
                    break

                try:
                    msg = msg.json()
                except ValueError:
                    disconnect_warn = 'Received invalid JSON.'
                    break

                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug("Received message:\n%s\n",
                                  pprint.pformat(msg))

                response = {
                    'msgid': msg['msgid'],
                }
                try:
                    result = yield from async_handle_message(
                        hass, self.cloud, msg['handler'], msg['payload'])

                    # No response from handler
                    if result is None:
                        continue

                    response['payload'] = result

                except UnknownHandler:
                    response['error'] = 'unknown-handler'

                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Error handling message")
                    response['error'] = 'exception'

                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug("Publishing message:\n%s\n",
                                  pprint.pformat(response))
                yield from client.send_json(response)

        except client_exceptions.WSServerHandshakeError as err:
            if err.code == 401:
                disconnect_warn = 'Invalid auth.'
                self.close_requested = True
                # Should we notify user?
            else:
                _LOGGER.warning("Unable to connect: %s", err)

        except client_exceptions.ClientError as err:
            _LOGGER.warning("Unable to connect: %s", err)

        finally:
            if disconnect_warn is None:
                _LOGGER.info("Connection closed")
            else:
                _LOGGER.warning("Connection closed: %s", disconnect_warn)

    @asyncio.coroutine
    def disconnect(self):
        """Disconnect the client."""
        self.close_requested = True

        if self.client is not None:
            yield from self.client.close()
        elif self.retry_task is not None:
            self.retry_task.cancel()


@asyncio.coroutine
def async_handle_message(hass, cloud, handler_name, payload):
    """Handle incoming IoT message."""
    handler = HANDLERS.get(handler_name)

    if handler is None:
        raise UnknownHandler()

    return (yield from handler(hass, cloud, payload))


@HANDLERS.register('alexa')
@asyncio.coroutine
def async_handle_alexa(hass, cloud, payload):
    """Handle an incoming IoT message for Alexa."""
    result = yield from alexa.async_handle_message(
        hass, cloud.alexa_config, payload)
    return result


@HANDLERS.register('google_actions')
@asyncio.coroutine
def async_handle_google_actions(hass, cloud, payload):
    """Handle an incoming IoT message for Google Actions."""
    result = yield from ga.async_handle_message(
        hass, cloud.gactions_config, payload)
    return result


@HANDLERS.register('cloud')
@asyncio.coroutine
def async_handle_cloud(hass, cloud, payload):
    """Handle an incoming IoT message for cloud component."""
    action = payload['action']

    if action == 'logout':
        yield from cloud.logout()
        _LOGGER.error("You have been logged out from Home Assistant cloud: %s",
                      payload['reason'])
    else:
        _LOGGER.warning("Received unknown cloud action: %s", action)

    return None
