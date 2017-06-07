"""
Support for Unifi WAP controllers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.unifi/
"""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.loader as loader
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.const import CONF_VERIFY_SSL

REQUIREMENTS = ['pyunifi==2.13']

_LOGGER = logging.getLogger(__name__)
CONF_PORT = 'port'
CONF_SITE_ID = 'site_id'

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8443
DEFAULT_VERIFY_SSL = True

NOTIFICATION_ID = 'unifi_notification'
NOTIFICATION_TITLE = 'Unifi Device Tracker Setup'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_SITE_ID, default='default'): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
})


def get_scanner(hass, config):
    """Set up the Unifi device_tracker."""
    from pyunifi.controller import Controller, APIError

    host = config[DOMAIN].get(CONF_HOST)
    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    site_id = config[DOMAIN].get(CONF_SITE_ID)
    port = config[DOMAIN].get(CONF_PORT)
    verify_ssl = config[DOMAIN].get(CONF_VERIFY_SSL)

    persistent_notification = loader.get_component('persistent_notification')
    try:
        ctrl = Controller(host, username, password, port, version='v4',
                          site_id=site_id, ssl_verify=verify_ssl)
    except APIError as ex:
        _LOGGER.error("Failed to connect to Unifi: %s", ex)
        persistent_notification.create(
            hass, 'Failed to connect to Unifi. '
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    return UnifiScanner(ctrl)


class UnifiScanner(DeviceScanner):
    """Provide device_tracker support from Unifi WAP client data."""

    def __init__(self, controller):
        """Initialize the scanner."""
        self._controller = controller
        self._update()

    def _update(self):
        """Get the clients from the device."""
        from pyunifi.controller import APIError
        try:
            clients = self._controller.get_clients()
        except APIError as ex:
            _LOGGER.error("Failed to scan clients: %s", ex)
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
        _LOGGER.debug("Device %s name %s", mac, name)
        return name
