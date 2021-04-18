"""Support for monitoring the rtorrent BitTorrent client API."""
import logging
import xmlrpc.client

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_URL, STATE_OFF, STATE_ON
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "rtorrent"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.url,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the rtorrent switch."""
    name = config[CONF_NAME]
    url = config[CONF_URL]

    try:
        rtorrent = xmlrpc.client.ServerProxy(url)
    except (xmlrpc.client.ProtocolError, ConnectionRefusedError) as ex:
        _LOGGER.error("Connection to rtorrent daemon failed")
        raise PlatformNotReady from ex

    add_entities([RTorrentSwitch(rtorrent, name)])


class RTorrentSwitch(ToggleEntity):
    """Representation of a rtorrent switch."""

    def __init__(self, xmlrpc_client, name):
        """Initialize the Deluge switch."""
        self._name = name
        self.xmlrpc_client = xmlrpc_client
        self._state = STATE_OFF
        self._available = False

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == STATE_ON

    @property
    def available(self):
        """Return true if device is available."""
        return self._available

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._switch_action("started", "d.resume=")

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._switch_action("started", "d.pause=")

    def update(self):
        """Get the latest data from rtorrent and updates the state."""

        data = self._switch_action("started", "d.is_active=")

        for torrent in data[0]:
            if torrent[0] == 1:
                self._state = STATE_ON
                return

        self._state = STATE_OFF

    def _switch_action(self, state, action):
        try:
            multicall = xmlrpc.client.MultiCall(self.xmlrpc_client)
            multicall.d.multicall2("", state, action)
            data = multicall()
            self._available = True
        except (xmlrpc.client.ProtocolError, ConnectionRefusedError, OSError) as ex:
            _LOGGER.error("Connection to rtorrent failed (%s)", ex)
            self._available = False
        return data