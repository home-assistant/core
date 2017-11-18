"""Module to handle messages from Home Assistant cloud."""
import asyncio
import logging

from aiohttp import hdrs, client_exceptions, WSMsgType

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.components.alexa import smart_home
from homeassistant.util.decorator import Registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from . import auth_api
from .const import MESSAGE_EXPIRATION


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
        hass = self.cloud.hass
        if self.cloud.subscription_expired:
            # Try refreshing the token to see if it is still expired.
            yield from hass.async_add_job(auth_api.check_token, self.cloud)

            if self.cloud.subscription_expired:
                hass.components.persistent_notification.async_create(
                    MESSAGE_EXPIRATION, 'Subscription expired',
                    'cloud_subscription_expired')
                self.state = STATE_DISCONNECTED
                return

        if self.state == STATE_CONNECTED:
            raise RuntimeError('Already connected')

        self.state = STATE_CONNECTING
        self.close_requested = False
        remove_hass_stop_listener = None
        session = async_get_clientsession(self.cloud.hass)
        client = None
        disconnect_warn = None

        @asyncio.coroutine
        def _handle_hass_stop(event):
            """Handle Home Assistant shutting down."""
            nonlocal remove_hass_stop_listener
            remove_hass_stop_listener = None
            yield from self.disconnect()

        try:
            yield from hass.async_add_job(auth_api.check_token, self.cloud)

            self.client = client = yield from session.ws_connect(
                self.cloud.relayer, headers={
                    hdrs.AUTHORIZATION:
                        'Bearer {}'.format(self.cloud.id_token)
                })
            self.tries = 0

            remove_hass_stop_listener = hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, _handle_hass_stop)

            _LOGGER.info('Connected')
            self.state = STATE_CONNECTED

            while not client.closed:
                msg = yield from client.receive()

                if msg.type in (WSMsgType.ERROR, WSMsgType.CLOSED,
                                WSMsgType.CLOSING):
                    disconnect_warn = 'Connection cancelled.'
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

                _LOGGER.debug('Received message: %s', msg)

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
                    _LOGGER.exception('Error handling message')
                    response['error'] = 'exception'

                _LOGGER.debug('Publishing message: %s', response)
                yield from client.send_json(response)

        except auth_api.CloudError:
            _LOGGER.warning('Unable to connect: Unable to refresh token.')

        except client_exceptions.WSServerHandshakeError as err:
            if err.code == 401:
                disconnect_warn = 'Invalid auth.'
                self.close_requested = True
                # Should we notify user?
            else:
                _LOGGER.warning('Unable to connect: %s', err)

        except client_exceptions.ClientError as err:
            _LOGGER.warning('Unable to connect: %s', err)

        except Exception:  # pylint: disable=broad-except
            if not self.close_requested:
                _LOGGER.exception('Unexpected error')

        finally:
            if disconnect_warn is not None:
                _LOGGER.warning('Connection closed: %s', disconnect_warn)

            if remove_hass_stop_listener is not None:
                remove_hass_stop_listener()

            if client is not None:
                self.client = None
                yield from client.close()

            if self.close_requested:
                self.state = STATE_DISCONNECTED

            else:
                self.state = STATE_CONNECTING
                self.tries += 1

                try:
                    # Sleep 0, 5, 10, 15 … up to 30 seconds between retries
                    self.retry_task = hass.async_add_job(asyncio.sleep(
                        min(30, (self.tries - 1) * 5), loop=hass.loop))
                    yield from self.retry_task
                    self.retry_task = None
                    hass.async_add_job(self.connect())
                except asyncio.CancelledError:
                    # Happens if disconnect called
                    pass

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
    return (yield from smart_home.async_handle_message(hass,
                                                       cloud.alexa_config,
                                                       payload))


@HANDLERS.register('cloud')
@asyncio.coroutine
def async_handle_cloud(hass, cloud, payload):
    """Handle an incoming IoT message for cloud component."""
    action = payload['action']

    if action == 'logout':
        yield from cloud.logout()
        _LOGGER.error('You have been logged out from Home Assistant cloud: %s',
                      payload['reason'])
    else:
        _LOGGER.warning('Received unknown cloud action: %s', action)

    return None
