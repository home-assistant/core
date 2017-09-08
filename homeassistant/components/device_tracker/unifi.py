"""
Support for Unifi WAP controllers.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.unifi/
"""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.const import CONF_VERIFY_SSL
import homeassistant.util.dt as dt_util
from datetime import timedelta
from enum import Enum

REQUIREMENTS = ['pyunifi==2.13']

_LOGGER = logging.getLogger(__name__)
CONF_PORT = 'port'
CONF_SITE_ID = 'site_id'
CONF_DETECTION_TIME = 'detection_time'
CONF_API_VERSION = 'api'

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8443
DEFAULT_VERIFY_SSL = True
DEFAULT_DETECTION_TIME = timedelta(seconds=300)
DEFAULT_API_VERSION = 'v4'

NOTIFICATION_ID = 'unifi_notification'
NOTIFICATION_TITLE = 'Unifi Device Tracker Setup'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_SITE_ID, default='default'): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    vol.Optional(CONF_DETECTION_TIME, default=DEFAULT_DETECTION_TIME): vol.All(
                     cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_API_VERSION, default=DEFAULT_API_VERSION): cv.string
})


def get_scanner(hass, config, ectrl=None):
    """Set up the Unifi device_tracker."""
    config = config[DOMAIN]
    print(config)
    result = None
    if ectrl is not None:
        _LOGGER.debug("ectrl found")
    try:
        result = UnifiScanner(config, ectrl=ectrl)
    except Exception as ex:
        hass.components.persistent_notification.create(
                'Failed to connect to Unifi. '
                'Error: {} <br />'
                'You will need to restart hass after fixing.'
                .format(ex),
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)
    return result


class UnifiScanner(DeviceScanner):
    """Provide device_tracker support from Unifi WAP client data."""

    def __init__(self, config, ectrl=None):
        """Initialize the scanner."""
        print(config)
        """Set up the Unifi device_tracker."""
        from pyunifi.controller import Controller, APIError
        _LOGGER.debug("pyunifi loaded")
        host = config.get(CONF_HOST)
        username = config.get(CONF_USERNAME)
        password = config.get(CONF_PASSWORD)
        site_id = config.get(CONF_SITE_ID)
        port = config.get(CONF_PORT)
        verify_ssl = config.get(CONF_VERIFY_SSL)
        detection_time = config.get(CONF_DETECTION_TIME)
        api_version = config.get(CONF_API_VERSION)

        if api_version != 'v4' and api_version != 'v5':
            _LOGGER.critical("Invalid API version")
            raise ValueError("Invalid API version")

        try:
            if ectrl is None:
                ctrl = Controller(host, username, password, port,
                                  version=api_version,
                                  site_id=site_id, ssl_verify=verify_ssl)
            else:
                _LOGGER.debug("External controller used")
                ctrl = ectrl(host, username, password, port,
                             version=api_version, site_id=site_id,
                             ssl_verify=verify_ssl)
            _LOGGER.info("Connection to controller successful")
            self._controller = ctrl
        except APIError as ex:
            _LOGGER.critical("Failed to connect to Unifi: %s", ex)
            raise Exception("Failed to connect to Unifi")

        self._detection_time = detection_time
        self._update()

    def _update(self):
        """Get the clients from the device."""
        _LOGGER.info("Updating client information")
        from pyunifi.controller import APIError
        try:
            clients = self._controller.get_clients()
            _LOGGER.debug("Found %d clients", len(clients))
        except APIError as ex:
            _LOGGER.critical("Failed to scan clients: %s", ex)
            clients = []

        self._clients = {
            client['mac']: client
            for client in clients
            if (dt_util.utcnow() - dt_util.utc_from_timestamp(float(
                client['last_seen']))) < self._detection_time
                }

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
