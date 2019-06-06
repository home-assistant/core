"""Support for Unifi WAP controllers."""
import asyncio
import logging
from datetime import timedelta
import voluptuous as vol

import async_timeout

import aiounifi

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.const import CONF_VERIFY_SSL, CONF_MONITORED_CONDITIONS
import homeassistant.util.dt as dt_util

from .controller import get_controller
from .errors import AuthenticationRequired, CannotConnect

_LOGGER = logging.getLogger(__name__)
CONF_PORT = 'port'
CONF_SITE_ID = 'site_id'
CONF_DETECTION_TIME = 'detection_time'
CONF_SSID_FILTER = 'ssid_filter'

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8443
DEFAULT_VERIFY_SSL = True
DEFAULT_DETECTION_TIME = timedelta(seconds=300)

NOTIFICATION_ID = 'unifi_notification'
NOTIFICATION_TITLE = 'Unifi Device Tracker Setup'

AVAILABLE_ATTRS = [
    '_id', '_is_guest_by_uap', '_last_seen_by_uap', '_uptime_by_uap',
    'ap_mac', 'assoc_time', 'authorized', 'bssid', 'bytes-r', 'ccq',
    'channel', 'essid', 'first_seen', 'hostname', 'idletime', 'ip',
    'is_11r', 'is_guest', 'is_wired', 'last_seen', 'latest_assoc_time',
    'mac', 'name', 'noise', 'noted', 'oui', 'powersave_enabled',
    'qos_policy_applied', 'radio', 'radio_proto', 'rssi', 'rx_bytes',
    'rx_bytes-r', 'rx_packets', 'rx_rate', 'signal', 'site_id',
    'tx_bytes', 'tx_bytes-r', 'tx_packets', 'tx_power', 'tx_rate',
    'uptime', 'user_id', 'usergroup_id', 'vlan'
]

TIMESTAMP_ATTRS = ['first_seen', 'last_seen', 'latest_assoc_time']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_SITE_ID, default='default'): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): vol.Any(
        cv.boolean, cv.isfile),
    vol.Optional(CONF_DETECTION_TIME, default=DEFAULT_DETECTION_TIME): vol.All(
        cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(AVAILABLE_ATTRS)]),
    vol.Optional(CONF_SSID_FILTER): vol.All(cv.ensure_list, [cv.string])
})


async def async_get_scanner(hass, config):
    """Set up the Unifi device_tracker."""
    host = config[DOMAIN].get(CONF_HOST)
    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    site_id = config[DOMAIN].get(CONF_SITE_ID)
    port = config[DOMAIN].get(CONF_PORT)
    verify_ssl = config[DOMAIN].get(CONF_VERIFY_SSL)
    detection_time = config[DOMAIN].get(CONF_DETECTION_TIME)
    monitored_conditions = config[DOMAIN].get(CONF_MONITORED_CONDITIONS)
    ssid_filter = config[DOMAIN].get(CONF_SSID_FILTER)

    try:
        controller = await get_controller(
            hass, host, username, password, port, site_id, verify_ssl)
        await controller.initialize()

    except (AuthenticationRequired, CannotConnect) as ex:
        _LOGGER.error("Failed to connect to Unifi: %s", ex)
        hass.components.persistent_notification.create(
            'Failed to connect to Unifi. '
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    return UnifiScanner(
        controller, detection_time, ssid_filter, monitored_conditions)


class UnifiScanner(DeviceScanner):
    """Provide device_tracker support from Unifi WAP client data."""

    def __init__(self, controller, detection_time: timedelta,
                 ssid_filter, monitored_conditions) -> None:
        """Initialize the scanner."""
        self.controller = controller
        self._detection_time = detection_time
        self._ssid_filter = ssid_filter
        self._monitored_conditions = monitored_conditions
        self._clients = {}

    async def async_update(self):
        """Get the clients from the device."""
        try:
            await self.controller.clients.update()
            clients = self.controller.clients.values()

        except aiounifi.LoginRequired:
            try:
                with async_timeout.timeout(5):
                    await self.controller.login()
            except (asyncio.TimeoutError, aiounifi.AiounifiException):
                clients = []

        except aiounifi.AiounifiException:
            clients = []

        # Filter clients to provided SSID list
        if self._ssid_filter:
            clients = [
                client for client in clients
                if client.essid in self._ssid_filter
            ]

        self._clients = {
            client.raw['mac']: client.raw
            for client in clients
            if (dt_util.utcnow() - dt_util.utc_from_timestamp(float(
                client.last_seen))) < self._detection_time
        }

    async def async_scan_devices(self):
        """Scan for devices."""
        await self.async_update()
        return self._clients.keys()

    def get_device_name(self, device):
        """Return the name (if known) of the device.

        If a name has been set in Unifi, then return that, else
        return the hostname if it has been detected.
        """
        client = self._clients.get(device, {})
        name = client.get('name') or client.get('hostname')
        _LOGGER.debug("Device mac %s name %s", device, name)
        return name

    def get_extra_attributes(self, device):
        """Return the extra attributes of the device."""
        if not self._monitored_conditions:
            return {}

        client = self._clients.get(device, {})
        attributes = {}
        for variable in self._monitored_conditions:
            if variable in client:
                if variable in TIMESTAMP_ATTRS:
                    attributes[variable] = dt_util.utc_from_timestamp(
                        float(client[variable])
                    )
                else:
                    attributes[variable] = client[variable]

        _LOGGER.debug("Device mac %s attributes %s", device, attributes)
        return attributes
