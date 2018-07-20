"""
Support for device tracking through Freebox routers.

This tracker keeps track of the devices connected to the configured Freebox.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.freebox/
"""
import asyncio
import copy
import logging
import socket
from collections import namedtuple
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
from homeassistant.const import (
    CONF_HOST, CONF_PORT)

REQUIREMENTS = ['aiofreepybox==0.0.4']

_LOGGER = logging.getLogger(__name__)

FREEBOX_CONFIG_FILE = 'freebox.conf'

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port
    }))

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up the Freebox device tracker and start the polling."""
    freebox_config = copy.deepcopy(config)
    if discovery_info is not None:
        freebox_config[CONF_HOST] = discovery_info['properties']['api_domain']
        freebox_config[CONF_PORT] = discovery_info['properties']['https_port']
        _LOGGER.info("Discovered Freebox server: %s:%s",
                     freebox_config[CONF_HOST], freebox_config[CONF_PORT])

    scanner = FreeboxDeviceScanner(hass, freebox_config, async_see)
    interval = freebox_config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    await scanner.async_start(hass, interval)
    return True


Device = namedtuple('Device', ['id', 'name', 'ip'])


def _build_device(device_dict):
    return Device(
        device_dict['l2ident']['id'],
        device_dict['primary_name'],
        device_dict['l3connectivities'][0]['addr'])


class FreeboxDeviceScanner:
    """This class scans for devices connected to the Freebox."""

    def __init__(self, hass, config, async_see):
        """Initialize the scanner."""
        from aiofreepybox import Freepybox

        self.host = config[CONF_HOST]
        self.port = config[CONF_PORT]
        self.token_file = hass.config.path(FREEBOX_CONFIG_FILE)
        self.async_see = async_see

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
        self.fbx = Freepybox(
            app_desc=app_desc,
            token_file=self.token_file,
            api_version=api_version)

    async def async_start(self, hass, interval):
        """Perform a first update and start polling at the given interval."""
        await self.async_update_info()
        interval = max(interval, MIN_TIME_BETWEEN_SCANS)
        async_track_time_interval(hass, self.async_update_info, interval)

    async def async_update_info(self, now=None):
        """Check the Freebox for devices."""
        from aiofreepybox.exceptions import HttpRequestError

        _LOGGER.info('Scanning devices')

        await self.fbx.open(self.host, self.port)
        try:
            hosts = await self.fbx.lan.get_hosts_list()
        except HttpRequestError:
            _LOGGER.exception('Failed to scan devices')
        else:
            active_devices = [_build_device(device)
                              for device in hosts
                              if device['active']]

            if active_devices:
                await asyncio.wait([self.async_see(mac=d.id, host_name=d.name)
                                    for d in active_devices])

        await self.fbx.close()
