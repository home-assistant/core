"""
Platform for the dGarage cover component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/dgarage/
"""
import logging
import bluetooth
from bluetooth import BluetoothSocket
import voluptuous as vol
import asyncio
import json
from homeassistant.const import (
    STATE_UNKNOWN, STATE_CLOSED, STATE_OPEN, CONF_COVERS,
    CONF_NAME, CONF_MAC, CONF_PORT, CONF_DEVICE_CLASS, STATE_OPENING)
from homeassistant.components.cover import (
    CoverDevice, SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_STOP,
    PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'dGarage'
STATE_IN_BETWEEN = "in_between"

STATES_MAP = {
    0: STATE_CLOSED,
    1: STATE_IN_BETWEEN,
    2: STATE_OPEN,
    3: STATE_UNKNOWN
}

COVER_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_MAC): cv.string,
    vol.Required(CONF_PORT): cv.positive_int,
    vol.Required(CONF_DEVICE_CLASS): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COVERS): vol.Schema({cv.slug: COVER_SCHEMA}),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up dGarage covers."""

    covers = []
    devices = config.get(CONF_COVERS)
    for device_id, device_config in devices.items():
        args = {
            CONF_NAME: device_config.get(CONF_NAME),
            CONF_MAC: device_config.get(CONF_MAC),
            CONF_PORT: device_config.get(CONF_PORT),
            CONF_DEVICE_CLASS: device_config.get(CONF_DEVICE_CLASS)
        }
        covers.append(dGarageCover(hass, args))

    async_add_devices(covers, True)


class dGarageCover(CoverDevice):
    """Representation of a dGarage cover."""

    # pylint: disable=no-self-use
    def __init__(self, hass, args):
        """Initialize the cover."""
        self.hass = hass
        self._name = args[CONF_NAME]
        self._mac = args[CONF_MAC]
        self._state = STATE_UNKNOWN
        self._port = args[CONF_PORT]
        self._socket = BluetoothSocket(bluetooth.RFCOMM)
        self._device_class = args[CONF_DEVICE_CLASS]

    @property
    def device_class(self):
        return self._device_class

    @property
    def name(self):
        return self._name

    @property
    def mac(self):
        return self._mac

    @property
    def supported_features(self):
        """Flag supported features"""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self._state in [STATE_UNKNOWN]:
            return None
        return self._state in [STATE_CLOSED]

    # @asyncio.coroutine
    # def async_update(self):
    #     """Retrieve latest state."""
    #     self._state = yield from self._update_state()

    @asyncio.coroutine
    def async_open_cover(self, **kwargs):
        """Open the cover."""
        if self._state not in [STATE_OPEN]:
            self._state = STATE_OPEN
        try:
            yield from self._send("{c:ope}")
        except bluetooth.BluetoothError as ex:
            self._do_except(ex)

    @asyncio.coroutine
    def async_close_cover(self, **kwargs):
        """Close the cover."""
        if self._state not in [STATE_CLOSED]:
            self._state = STATE_CLOSED
        try:
            yield from self._send("{c:clo}")
        except bluetooth.BluetoothError as ex:
            self._do_except(ex)

    @asyncio.coroutine
    def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        if self._state not in [STATE_IN_BETWEEN]:
            self._state = STATE_OPENING
        try:
            yield from self._send("{c:sto}")
        except bluetooth.BluetoothError as ex:
            self._do_except(ex)

    async def _send(self, message):
        self._socket.connect((self._mac, self._port))
        self._socket.send(message)
        self._socket.close()
        self._socket = BluetoothSocket(bluetooth.RFCOMM)

    def _do_except(self, reason):
        _LOGGER.error("Unable to connect to dGarage device: %(reason)s",
                      dict(reason=reason))

    @asyncio.coroutine
    def _update_state(self):
        # http://pages.iu.edu/~rwisman/c490/html/pythonandbluetooth.htm
        yield from self._send("{g}")

        self._socket.bind(("", self._port))
        self._socket.listen(1)

        client_socket, address = self._socket.accept()
        data = client_socket.recv(1024)
        # for ch in data:
        #     if ch == "{":
        #
        # https://stackoverflow.com/questions/17667903/python-socket-receive-large-amount-of-data
        # ?utm_medium=organic&utm_source=google_rich_qa&utm_campaign=google_rich_qa

        parsed = json.loads(data)
        self._state = parsed['doorStateIndicator']

        client_socket.close()
        self._socket.close()
        self._socket = BluetoothSocket(bluetooth.RFCOMM)