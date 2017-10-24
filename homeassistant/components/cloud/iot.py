"""Module to handle messages from Home Assistant cloud."""
import asyncio
import logging

from aiohttp import hdrs, client_exceptions, WSMsgType

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.components.alexa import smart_home
from homeassistant.util.decorator import Registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from . import auth_api


HANDLERS = Registry()
_LOGGER = logging.getLogger(__name__)


class UnknownHandler(Exception):
    """Exception raised when trying to handle unknown handler."""


class CloudIoT:
    """Class to manage the IoT connection."""

    def __init__(self, cloud):
        """Initialize the CloudIoT class."""
        self.cloud = cloud
        self.client = None
        self.close_requested = False
        self.tries = 0

    @property
    def is_connected(self):
        """Return if connected to the cloud."""
        return self.client is not None

    @asyncio.coroutine
    def connect(self):
        """Connect to the IoT broker."""
        if self.client is not None:
            raise RuntimeError('Cannot connect while already connected')

        self.close_requested = False

        hass = self.cloud.hass
        remove_hass_stop_listener = None

        session = async_get_clientsession(self.cloud.hass)

        @asyncio.coroutine
        def _handle_hass_stop(event):
            """Handle Home Assistant shutting down."""
            nonlocal remove_hass_stop_listener
            remove_hass_stop_listener = None
            yield from self.disconnect()

        client = None
        disconnect_warn = None
        try:
            yield from hass.async_add_job(auth_api.check_token, self.cloud)

            self.client = client = yield from session.ws_connect(
                self.cloud.relayer, headers={
                    hdrs.AUTHORIZATION:
                        'Bearer {}'.format(self.cloud.access_token)
                })
            self.tries = 0

            remove_hass_stop_listener = hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, _handle_hass_stop)

            _LOGGER.info('Connected')

            while not client.closed:
                msg = yield from client.receive()

                if msg.type in (WSMsgType.ERROR, WSMsgType.CLOSED,
                                WSMsgType.CLOSING):
                    disconnect_warn = 'Closed by server'
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

            if not self.close_requested:
                self.tries += 1

                # Sleep 0, 5, 10, 15 … up to 30 seconds between retries
                yield from asyncio.sleep(
                    min(30, (self.tries - 1) * 5), loop=hass.loop)

                hass.async_add_job(self.connect())

    @asyncio.coroutine
    def disconnect(self):
        """Disconnect the client."""
        self.close_requested = True
        yield from self.client.close()


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
    return (yield from smart_home.async_handle_message(hass, payload))


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
