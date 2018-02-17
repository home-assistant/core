"""
Support for device tracking through Freebox routers.

This tracker keeps track of the devices connected to the configured Freebox.

Example configuration.yaml entry:

device_tracker:
  - platform: freebox
    host: foobar.fbox.fr
    port: 1234

You can find out your Freebox host and port by opening this address in your
browser: http://mafreebox.freebox.fr/api_version. The returned json should
contain an api_domain (host) and a https_port (port).

The first time you add your Freebox, you will need to authorize Home Assistant
by pressing the right button on the facade of the Freebox when prompted to do
so.

Note that the Freebox waits for some time before marking a device as
inactive, meaning that there will be a small delay (1 or 2 minutes)
between the time you disconnect a device and the time it will appear
as "away" in Hass. You should take this into account when specifying
consider_home.
On the contrary, the Freebox immediately reports devices newly connected, so
they should appear as "home" almost instantly, as soon as Hass refreshes the
devices states.

"""
import logging
from collections import namedtuple
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PORT)
from homeassistant.util import Throttle

REQUIREMENTS = ['freepybox==0.0.3']

_LOGGER = logging.getLogger(__name__)

FREEBOX_CONFIG_FILE = 'freebox.conf'

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port
    }))

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


def get_scanner(hass, config):
    """Validate the configuration and return a Bbox scanner."""
    scanner = FreeboxDeviceScanner(hass, config[DOMAIN])

    return scanner if scanner.success_init else None


Device = namedtuple('Device', ['id', 'name', 'ip'])


def _build_device(device_dict):
    return Device(
            device_dict['l2ident']['id'],
            device_dict['primary_name'],
            device_dict['l3connectivities'][0]['addr'])


class FreeboxDeviceScanner(DeviceScanner):
    """This class scans for devices connected to the Freebox."""

    def __init__(self, hass, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.port = config[CONF_PORT]
        self.token_file = hass.config.path(FREEBOX_CONFIG_FILE)

        self.last_results = []  # type: List[Device]

        self.success_init = self._update_info()
        _LOGGER.info("Scanner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        _LOGGER.info("Devices detected: " + str([device.name for device in self.last_results]))
        return [device.id for device in self.last_results]

    def get_device_name(self, id):
        """Return the name of the given device or None if we don't know."""
        for device in self.last_results:
            if device.id == id:
                return device.name

        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Check the Freebox for devices.

        Returns boolean if scanning successful.
        """
        _LOGGER.info('Scanning devices')

        from freepybox import Freepybox
        import socket

        # Hardcode the app description to avoid invalidating the authentication
        # file at each new version.
        # The version can be changed if we want the user to re-authorize HASS
        # on her Freebox.
        app_desc = {
            'app_id': 'hass',
            'app_name': 'Home Assistant',
            'app_version': '0.65',
            'device_name': socket.gethostname()
        }

        api_version = 'v1'  # Use the lowest working version.
        fbx = Freepybox(
            app_desc=app_desc,
            token_file=self.token_file,
            api_version=api_version)
        fbx.open(self.host, self.port)
        try:
            hosts = fbx.lan.get_hosts_list()
        finally:
            fbx.close()

        last_results = [_build_device(device)
                        for device in hosts
                        if device['active']]

        self.last_results = last_results

        _LOGGER.info('Scan successful')
        return True
