"""
Support for FRITZ!Box routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.fritz/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

REQUIREMENTS = ['fritzconnection==0.6.5']

_LOGGER = logging.getLogger(__name__)

CONF_DEFAULT_IP = '169.254.1.1'  # This IP is valid for all FRITZ!Box routers.

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=CONF_DEFAULT_IP): cv.string,
    vol.Optional(CONF_PASSWORD, default='admin'): cv.string,
    vol.Optional(CONF_USERNAME, default=''): cv.string
})


def get_scanner(hass, config):
    """Validate the configuration and return FritzBoxScanner."""
    scanner = FritzBoxScanner(config[DOMAIN])
    return scanner if scanner.success_init else None


class FritzBoxScanner(DeviceScanner):
    """This class queries a FRITZ!Box router."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.last_results = []
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.success_init = True

        import fritzconnection as fc  # pylint: disable=import-error

        # Establish a connection to the FRITZ!Box.
        try:
            self.fritz_box = fc.FritzHosts(
                address=self.host, user=self.username, password=self.password)
        except (ValueError, TypeError):
            self.fritz_box = None

        # At this point it is difficult to tell if a connection is established.
        # So just check for null objects.
        if self.fritz_box is None or not self.fritz_box.modelname:
            self.success_init = False

        if self.success_init:
            _LOGGER.info("Successfully connected to %s",
                         self.fritz_box.modelname)
            self._update_info()
        else:
            _LOGGER.error("Failed to establish connection to FRITZ!Box "
                          "with IP: %s", self.host)

    def scan_devices(self):
        """Scan for new devices and return a list of found device ids."""
        self._update_info()
        active_hosts = []
        for known_host in self.last_results:
            if known_host['status'] == '1' and known_host.get('mac'):
                active_hosts.append(known_host['mac'])
        return active_hosts

    def get_device_name(self, device):
        """Return the name of the given device or None if is not known."""
        ret = self.fritz_box.get_specific_host_entry(device).get(
            'NewHostName'
        )
        if ret == {}:
            return None
        return ret

    def _update_info(self):
        """Retrieve latest information from the FRITZ!Box."""
        if not self.success_init:
            return False

        _LOGGER.info("Scanning")
        self.last_results = self.fritz_box.get_hosts_info()
        return True
