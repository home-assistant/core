"""
Support for setting the Deluge BitTorrent client in Pause.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.deluge/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, CONF_PASSWORD, CONF_USERNAME, STATE_OFF,
    STATE_ON)
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['deluge-client==1.2.0']

_LOGGING = logging.getLogger(__name__)

DEFAULT_NAME = 'Deluge Switch'
DEFAULT_PORT = 58846

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Deluge switch."""
    from deluge_client import DelugeRPCClient

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    port = config.get(CONF_PORT)

    deluge_api = DelugeRPCClient(host, port, username, password)

    add_devices([DelugeSwitch(deluge_api, name)])


class DelugeSwitch(ToggleEntity):
    """Representation of a Deluge switch."""

    def __init__(self, deluge_client, name):
        """Initialize the Deluge switch."""
        self._name = name
        self.deluge_client = deluge_client
        self._state = STATE_OFF
        self._available = False

        try:
            self.deluge_client.connect()
            self._available = True
        except ConnectionRefusedError:
            _LOGGING.error("Connection to Deluge Daemon failed")
            return

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
        # self.deluge_client.call('core.resume_all_torrents')
        torrent_ids = self.deluge_client.call('core.get_session_state')
        self.deluge_client.call('core.resume_torrent', torrent_ids)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        # self.deluge_client.call('core.pause_all_torrents')
        torrent_ids = self.deluge_client.call('core.get_session_state')
        self.deluge_client.call('core.pause_torrent', torrent_ids)

    def update(self):
        """ check if deluge_client is connected first """
        try:
            self.deluge_client._create_socket()
            self.deluge_client.connect()
            self._available = True
        except ConnectionRefusedError:
            _LOGGING.error("Connection to Deluge Daemon failed")
            self._available = False
            return

        """Get the latest data from deluge and updates the state."""
        torrent_list = self.deluge_client.call('core.get_torrents_status', {},
                                               ['paused'])
        for torrent in torrent_list.values():
            item = torrent.popitem()
            if not item[1]:
                self._state = STATE_ON
                return

        self._state = STATE_OFF
