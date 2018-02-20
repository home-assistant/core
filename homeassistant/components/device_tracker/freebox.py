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
import copy
import logging
from collections import namedtuple
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_time_interval
from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
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


def setup_scanner(hass, config, see, discovery_info=None):
    freebox_config = copy.deepcopy(config)
    if discovery_info is not None:
        freebox_config[CONF_HOST] = discovery_info['properties']['api_domain']
        freebox_config[CONF_PORT] = discovery_info['properties']['https_port']
        _LOGGER.info("Discovered Freebox server: %s:%s",
                     freebox_config[CONF_HOST], freebox_config[CONF_PORT])

    FreeboxDeviceScanner(hass, freebox_config, see)
    return True


Device = namedtuple('Device', ['id', 'name', 'ip'])


def _build_device(device_dict):
    return Device(
            device_dict['l2ident']['id'],
            device_dict['primary_name'],
            device_dict['l3connectivities'][0]['addr'])


class FreeboxDeviceScanner(object):
    """This class scans for devices connected to the Freebox."""

    def __init__(self, hass, config, see):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.port = config[CONF_PORT]
        self.token_file = hass.config.path(FREEBOX_CONFIG_FILE)

        self.see = see

        self.update_info()

        interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        track_time_interval(hass, self.update_info, interval)

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def update_info(self, now=None):
        """Check the Freebox for devices."""
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

        for d in last_results:
            self.see(mac=d.id, host_name=d.name)

        return True
