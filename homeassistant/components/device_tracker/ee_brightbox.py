"""
Support for EE Brightbox router.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.ee_brightbox/
"""

import logging
import datetime

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_USERNAME, CONF_PASSWORD)

REQUIREMENTS = ['eebrightbox==0.0.4', 'timeago==1.0.8']

_LOGGER = logging.getLogger(__name__)

CONF_VERSION = 'version'

CONF_DEFAULT_IP = '192.168.1.1'
CONF_DEFAULT_USERNAME = 'admin'
CONF_DEFAULT_VERSION = 2

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_VERSION, default=CONF_DEFAULT_VERSION): cv.positive_int,
    vol.Required(CONF_HOST, default=CONF_DEFAULT_IP): cv.string,
    vol.Required(CONF_USERNAME, default=CONF_DEFAULT_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def get_scanner(hass, config):
    """Return a router scanner instance."""
    return EEBrightBoxScanner(config[DOMAIN])


class EEBrightBoxScanner(DeviceScanner):
    """Scan EE Brightbox router."""

    def __init__(self, config):
        """Initialise the scanner."""
        self.config = config
        self.devices = {}

    def scan_devices(self):
        """Scan for devices."""
        from eebrightbox import EEBrightBox

        with EEBrightBox(self.config) as ee_brightbox:
            self.devices = {d['mac']: d for d in ee_brightbox.get_devices()}

        macs = [d['mac'] for d in self.devices.values() if d['activity_ip']]

        _LOGGER.debug('Scan devices %s', macs)

        return macs

    def get_device_name(self, device):
        """Get the name of a device from hostname."""
        if device in self.devices:
            return self.devices[device]['hostname'] or None

        return None

    def get_extra_attributes(self, device):
        """
        Get the extra attributes of a device.

        Extra attributes include:
        - ip
        - mac
        - port - ethX or wifiX
        - last active
        """
        import timeago

        port_map = {
            'wl1': 'wifi5Ghz',
            'wl0': 'wifi2.4Ghz',
            'eth0': 'eth0',
            'eth1': 'eth1',
            'eth2': 'eth2',
            'eth3': 'eth3',
        }

        if device in self.devices:
            return {
                'ip': self.devices[device]['ip'],
                'mac': self.devices[device]['mac'],
                'port': port_map[self.devices[device]['port']],
                'last active': timeago.format(
                    self.devices[device]['time_last_active'],
                    datetime.datetime.now()
                ),
            }

        return {}
