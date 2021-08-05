"""Support for setting the Deluge BitTorrent client in Pause."""
import logging

from deluge_client import DelugeRPCClient, FailedToReconnectException
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Deluge Switch"
DEFAULT_PORT = 58846

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Deluge switch."""

    name = config[CONF_NAME]
    host = config[CONF_HOST]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    port = config[CONF_PORT]

    deluge_api = DelugeRPCClient(host, port, username, password)
    try:
        deluge_api.connect()
    except ConnectionRefusedError as err:
        _LOGGER.error("Connection to Deluge Daemon failed")
        raise PlatformNotReady from err

    add_entities([DelugeSwitch(deluge_api, name)])


class DelugeSwitch(ToggleEntity):
    """Representation of a Deluge switch."""

    def __init__(self, deluge_client, name):
        """Initialize the Deluge switch."""
        self._name = name
        self.deluge_client = deluge_client
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
        torrent_ids = self.deluge_client.call("core.get_session_state")
        self.deluge_client.call("core.resume_torrent", torrent_ids)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        torrent_ids = self.deluge_client.call("core.get_session_state")
        self.deluge_client.call("core.pause_torrent", torrent_ids)

    def update(self):
        """Get the latest data from deluge and updates the state."""

        try:
            torrent_list = self.deluge_client.call(
                "core.get_torrents_status", {}, ["paused"]
            )
            self._available = True
        except FailedToReconnectException:
            _LOGGER.error("Connection to Deluge Daemon Lost")
            self._available = False
            return
        for torrent in torrent_list.values():
            item = torrent.popitem()
            if not item[1]:
                self._state = STATE_ON
                return

        self._state = STATE_OFF
