"""
Component to create an interface to the Loxone Miniserver

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/loxone/
"""
# pylint: disable=unused-import, too-many-lines
import asyncio
import codecs
import hashlib
import hmac
import logging
import uuid
import json
from datetime import timedelta
from struct import unpack

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_HOST, CONF_PORT, CONF_USERNAME,
                                 CONF_PASSWORD)
from homeassistant.helpers.event import async_track_time_interval

REQUIREMENTS = ['websockets==3.4']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'loxone'
DEFAULT_PORT = 80
EVENT = 'loxone_received'

KEEPALIVEINTERVAL = timedelta(seconds=120)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }),
}, extra=vol.ALLOW_EXTRA)

DEFAULT = ""
ATTR_UUID = 'uuid'
ATTR_VALUE = 'value'

@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Loxone component."""
    user = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    host = config[DOMAIN][CONF_HOST]
    port = config[DOMAIN][CONF_PORT]
    api = LoxoneGateway(hass, user, password, host, port)
    api.start_listener(api.get_process_message_callback())
    async_track_time_interval(hass, api.send_keepalive, KEEPALIVEINTERVAL)

    @asyncio.coroutine
    def handle_event_bus_command(call):
        """Handle event bus services."""
        value = call.data.get(ATTR_VALUE, DEFAULT)
        device_uuid = call.data.get(ATTR_UUID, DEFAULT)
        data = {device_uuid: value}
        hass.bus.async_fire(EVENT, data)

    hass.services.async_register(DOMAIN, 'event_bus_command',
                                 handle_event_bus_command)

    @asyncio.coroutine
    def handle_websocket_command(call):
        """Handle websocket command services."""
        value = call.data.get(ATTR_VALUE, DEFAULT)
        device_uuid = call.data.get(ATTR_UUID, DEFAULT)
        yield from api.send_websocket_command(device_uuid, value)

    hass.services.async_register(DOMAIN, 'event_websocket_command',
                                 handle_websocket_command)

    return True


class LoxoneGateway:
    """ Main class for the communication with the miniserver """
    def __init__(self, hass, user, password, host, port):
        """ Username, password, host and port of a Loxone user """
        self._hass = hass
        self._user = user
        self._password = password
        self._host = host
        self._port = port
        self._ws = None
        self._current_typ = None

    @asyncio.coroutine
    def send_websocket_command(self, device_uuid, value):
        """ Send a websocket command to the Miniserver """
        yield from self._ws.send(
            "jdev/sps/io/{}/{}".format(device_uuid, value))

    def get_process_message_callback(self):
        """Function to be called when data is received."""
        return self._async_process_message

    def start_listener(self, async_callback):
        """Start the websocket listener."""
        try:
            from asyncio import ensure_future
        except ImportError:
            from asyncio import async as ensure_future
        # pylint: disable=deprecated-method
        ensure_future(self._ws_listen(async_callback))

    @asyncio.coroutine
    def send_keepalive(self, _):
        """Send an keep alive to the Miniserver."""
        _LOGGER.debug("Keep alive send")
        yield from self._ws.send("keepalive")

    @asyncio.coroutine
    def _ws_read(self):
        """ Establish the connection an read the messages"""
        import websockets as wslib
        try:
            if not self._ws:
                self._ws = yield from wslib.connect(
                    "ws://{}:{}/ws/rfc6455".format(self._host, self._port),
                    timeout=5)
                yield from self._ws.send("jdev/sys/getkey")
                yield from self._ws.recv()
                key = yield from self._ws.recv()
                yield from self._ws.send("authenticate/{}".format(get_hash(
                    key, self._user, self._password)))
                yield from self._ws.recv()
                yield from self._ws.send("jdev/sps/enablebinstatusupdate")
                yield from self._ws.recv()
        except Exception as ws_exc:  # pylint: disable=broad-except
            _LOGGER.error("Failed to connect to websocket: %s", ws_exc)
            return

        result = None
        try:
            result = yield from self._ws.recv()
        except Exception as ws_exc:  # pylint: disable=broad-except
            _LOGGER.error("Failed to read from websocket: %s", ws_exc)
            try:
                yield from self._ws.close()
            finally:
                self._ws = None
        return result

    @asyncio.coroutine
    def _ws_listen(self, async_callback):
        """ Listen to all commands from the Miniserver"""
        try:
            while True:
                result = yield from self._ws_read()
                if result:
                    yield from _ws_process_message(result, async_callback)
                else:
                    _LOGGER.debug("Trying again in 30 seconds.")
                    yield from asyncio.sleep(30)
        finally:
            print("CLOSED")
            if self._ws:
                yield from self._ws.close()

    @asyncio.coroutine
    def _async_process_message(self, message):
        """ Process the messages """
        if len(message) == 8:
            unpacked_data = unpack('ccccI', message)
            self._current_typ = int.from_bytes(unpacked_data[1],
                                               byteorder='big')
        else:
            parsed_data = parse_loxone_message(self._current_typ, message)
            _LOGGER.debug(parsed_data)
            self._hass.bus.async_fire(EVENT, parsed_data)


@asyncio.coroutine
def _ws_process_message(message, async_callback):
    """ Process the messages """
    try:
        yield from async_callback(message)
    except:  # pylint: disable=bare-except
        _LOGGER.exception("Exception in callback, ignoring.")


def get_hash(key, username, password):
    """ Get the login data from username and password """
    key_dict = json.loads(key)
    key_value = key_dict['LL']['value']
    data = "{}:{}".format(username, password)
    decoded_key = codecs.decode(key_value.encode("ascii"), "hex")
    hmac_obj = hmac.new(decoded_key, data.encode('UTF-8'), hashlib.sha1)
    return hmac_obj.hexdigest()


def parse_loxone_message(typ, message):
    """ Parser of the Loxone message """
    event_dict = {}
    if typ == 0:
        _LOGGER.debug("Text Message received!!")
        event_dict = message
    elif typ == 1:
        _LOGGER.debug("Binary Message received!!")
    elif typ == 2:
        _LOGGER.debug("Event-Table of Value-States received!!")
        length = len(message)
        num = length / 24
        start = 0
        end = 24
        # pylint: disable=unused-variable
        for i in range(int(num)):
            packet = message[start:end]
            event_uuid = uuid.UUID(bytes_le=packet[0:16])
            fields = event_uuid.urn.replace("urn:uuid:", "").split("-")
            uuidstr = "{}-{}-{}-{}-{}".format(fields[0], fields[1], fields[2],
                                              fields[3], fields[4])
            value = unpack('d', packet[16:24])[0]
            event_dict[uuidstr] = value
            start += 24
            end += 24
    elif typ == 3:
        pass
    elif typ == 6:
        _LOGGER.debug("Keep alive Message received!")
    return event_dict
