"""
Platform for the Garadget cover component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/dgarage/
"""
import logging
import bluetooth
from bluetooth import BluetoothSocket
import voluptuous as vol
import json
import asyncio
from homeassistant.const import (
    STATE_UNKNOWN, STATE_CLOSED, STATE_OPEN, CONF_COVERS,
    CONF_NAME, CONF_MAC, CONF_PORT, CONF_DEVICE_CLASS)
from homeassistant.components.cover import (
    CoverDevice, SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_STOP,
    PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'dGarage'
STATE_STOPPED = "stopped"
CONF_HOST_MAC = "host_mac"

STATES_MAP = {
    0: STATE_CLOSED,
    1: STATE_STOPPED,
    2: STATE_OPEN,
    3: STATE_UNKNOWN
}

COVER_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_MAC): cv.string,
    vol.Required(CONF_PORT): cv.positive_int,
    vol.Required(CONF_DEVICE_CLASS): cv.string,
    vol.Required(CONF_HOST_MAC): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COVERS): vol.Schema({cv.slug: COVER_SCHEMA}),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
# def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up dGarage covers."""

    covers = []
    devices = config.get(CONF_COVERS)
    for device_id, device_config in devices.items():
        args = {
            CONF_NAME: device_config.get(CONF_NAME),
            CONF_MAC: device_config.get(CONF_MAC),
            CONF_PORT: device_config.get(CONF_PORT),
            CONF_DEVICE_CLASS: device_config.get(CONF_DEVICE_CLASS),
            CONF_HOST_MAC: device_config.get(CONF_HOST_MAC)
        }
        covers.append(dGarageCover(hass, args))

    # add_devices(covers, True)
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
        self._socket = None
        self._device_class = args[CONF_DEVICE_CLASS]
        self._host_mac = args[CONF_HOST_MAC]

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
        return self._state == STATE_CLOSED

    @asyncio.coroutine
    def async_update(self):
        """Retrieve latest state."""
        self._state = yield from self.async_fetch_state()

    @asyncio.coroutine
    def async_open_cover(self, **kwargs):
        """Open the cover."""
        try:
            # self._send("{c:ope}")
            yield from self._send("{c:ope}")
            if self._state not in [STATE_OPEN]:
                self._state = STATE_OPEN
        except bluetooth.BluetoothError as ex:
            self._do_except(ex)

    @asyncio.coroutine
    def async_close_cover(self, **kwargs):
        """Close the cover."""
        try:
            # self._send("{c:clo}")
            yield from self._send("{c:clo}")
            if self._state not in [STATE_CLOSED]:
                self._state = STATE_CLOSED
        except bluetooth.BluetoothError as ex:
            self._do_except(ex)

    @asyncio.coroutine
    def async_stop_cover(self, **kwargs):
        # def stop_cover(self, **kwargs):
        """Stop the cover."""
        try:
            # self._send("{c:sto}")
            yield from self._send("{c:sto}")
            if self._state not in [STATE_STOPPED]:
                self._state = STATE_STOPPED
        except bluetooth.BluetoothError as ex:
            self._do_except(ex)

    # def _send(self, message):
    async def _send(self, message):
        self._socket = BluetoothSocket(bluetooth.RFCOMM)
        self._socket.connect((self._mac, self._port))
        self._socket.send(message)
        self._socket.close()
        self._socket = None

    def _do_except(self, reason):
        _LOGGER.error("Unable to connect to dGarage device: %(reason)s",
                      dict(reason=reason))

    @asyncio.coroutine
    # def _update_state(self):
    async def async_fetch_state(self):
        try:
            self._socket = BluetoothSocket(bluetooth.RFCOMM)
            self._socket.connect((self._mac, self._port))
            self._socket.send("{g}")
        except bluetooth.BluetoothError as ex:
            self._socket.close()
            self._socket = None
            return self._state

        s = BluetoothSocket(bluetooth.RFCOMM)
        s.bind((self._host_mac, self._port))
        s.listen(1)

        try:
            while 1:
                data = self._socket.recv(1024)
                data = data.decode("utf-8")
                if data:
                    parsed = json.loads(data)
                    settings = parsed['ard_settings']
                    door_state_indicator = settings['doorStateIndicator']
                    state = STATES_MAP[int(door_state_indicator)]
                    break

            self._socket.close()
            self._socket = None
            s.close()
            return state
        except:
            self._socket.close()
            self._socket = None
            s.close()
