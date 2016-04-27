"""
Support for Unifi WAP controllers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.unifi/
"""
import logging
import urllib

from homeassistant.components.device_tracker import DOMAIN
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import validate_config

# Unifi package doesn't list urllib3 as a requirement
REQUIREMENTS = ['urllib3', 'unifi==1.2.5']

_LOGGER = logging.getLogger(__name__)
CONF_PORT = 'port'


def get_scanner(hass, config):
    """Setup Unifi device_tracker."""
    from unifi.controller import Controller

    if not validate_config(config, {DOMAIN: [CONF_USERNAME,
                                             CONF_PASSWORD]},
                           _LOGGER):
        _LOGGER.error('Invalid configuration')
        return False

    this_config = config[DOMAIN]
    host = this_config.get(CONF_HOST, 'localhost')
    username = this_config.get(CONF_USERNAME)
    password = this_config.get(CONF_PASSWORD)

    try:
        port = int(this_config.get(CONF_PORT, 8443))
    except ValueError:
        _LOGGER.error('Invalid port (must be numeric like 8443)')
        return False

    try:
        ctrl = Controller(host, username, password, port, 'v4')
    except urllib.error.HTTPError as ex:
        _LOGGER.error('Failed to connect to unifi: %s', ex)
        return False

    return UnifiScanner(ctrl)


class UnifiScanner(object):
    """Provide device_tracker support from Unifi WAP client data."""

    def __init__(self, controller):
        """Initialize the scanner."""
        self._controller = controller
        self._update()

    def _update(self):
        """Get the clients from the device."""
        try:
            clients = self._controller.get_clients()
        except urllib.error.HTTPError as ex:
            _LOGGER.error('Failed to scan clients: %s', ex)
            clients = []

        self._clients = {client['mac']: client for client in clients}

    def scan_devices(self):
        """Scan for devices."""
        self._update()
        return self._clients.keys()

    def get_device_name(self, mac):
        """Return the name (if known) of the device.

        If a name has been set in Unifi, then return that, else
        return the hostname if it has been detected.
        """
        client = self._clients.get(mac, {})
        name = client.get('name') or client.get('hostname')
        _LOGGER.debug('Device %s name %s', mac, name)
        return name
