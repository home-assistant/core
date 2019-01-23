"""Support for EE Brightbox router."""
import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, SCAN_INTERVAL, SOURCE_TYPE_ROUTER, DeviceScanner,
    DeviceTrackerEntity)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an EE Brightbox device tracker platform."""
    scanner = EEBrightBoxScanner(config)
    if not scanner.check_config():
        return
    entities = []
    devices = scanner.scan_devices()
    for mac in devices:
        name = scanner.get_device_name(mac)
        entities.append(EEBrightBoxEntity(mac, name, scanner))

    add_entities(entities, True)


class EEBrightBoxEntity(DeviceTrackerEntity):
    """Represent an EE Brightbox router entity."""

    def __init__(self, mac, name, scanner):
        """Set up the entity."""
        self._attrs = None
        self._is_connected = None
        self._mac = mac
        self._name = name
        self._scanner = scanner

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return self._attrs

    @property
    def is_connected(self):
        """Return True if device is connected."""
        return self._is_connected

    @property
    def mac_address(self):
        """Return the mac address of the device."""
        return self._mac

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_ROUTER

    def update(self):
        """Update state of entity."""
        self._scanner.scan_devices()
        macs = [
            d['mac'] for d in self._scanner.devices.values()
            if d['activity_ip']]
        self._is_connected = self._mac in macs
        self._attrs = self._scanner.get_extra_attributes(self._mac)


class EEBrightBoxScanner(DeviceScanner):
    """Scan EE Brightbox router."""

    def __init__(self, config):
        """Initialise the scanner."""
        self.config = config
        self.devices = {}

    def check_config(self):
        """Check if provided configuration and credentials are correct."""
        from eebrightbox import EEBrightBox, EEBrightBoxException

        try:
            with EEBrightBox(self.config) as ee_brightbox:
                return bool(ee_brightbox.get_devices())
        except EEBrightBoxException:
            _LOGGER.exception("Failed to connect to the router")
            return False

    @Throttle(SCAN_INTERVAL)
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
        - last_active
        """
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
                'last_active': self.devices[device]['time_last_active'],
            }

        return {}
