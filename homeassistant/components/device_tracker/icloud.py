"""
homeassistant.components.device_tracker.icloud
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Device tracker platform that supports scanning a iCloud devices.

It does require that your device has registered with Find My iPhone.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.icloud/
"""
import logging
from datetime import timedelta
import threading

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle
from homeassistant.components.device_tracker import DOMAIN

import re

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['https://github.com/picklepete/pyicloud/archive/'
                '80f6cd6decc950514b8dc43b30c5bded81b34d5f.zip'
                '#pyicloud==0.8.0',
                'certifi']


def get_scanner(hass, config):
    """ Validates config and returns a iPhone Scanner. """
    if not validate_config(config,
                           {DOMAIN: [CONF_USERNAME, CONF_PASSWORD]},
                           _LOGGER):
        return None

    scanner = ICloudDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class ICloudDeviceScanner(object):
    """
    This class looks up devices from your iCloud account
    and can report on their lat and long if registered.
    """

    def __init__(self, config):
        from pyicloud import PyiCloudService
        from pyicloud.exceptions import PyiCloudFailedLoginException
        from pyicloud.exceptions import PyiCloudNoDevicesException

        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.lock = threading.Lock()

        self.last_results = {}

        # Get the data from iCloud
        try:
            _LOGGER.info('Logging into iCloud Services')
            self._api = PyiCloudService(self.username,
                                        self.password,
                                        verify=True)
        except PyiCloudFailedLoginException:
            _LOGGER.exception("Failed login to iCloud Service." +
                              "Verify Username and Password")
            return

        try:
            devices = self.get_devices()
        except PyiCloudNoDevicesException:
            _LOGGER.exception("No iCloud Devices found.")
            return

        self.success_init = devices is not None

        if self.success_init:
            self.last_results = devices
        else:
            _LOGGER.error('Issues getting iCloud results')

    def scan_devices(self):
        """
        Scans for new devices and return a list containing found devices id's
        """

        self._update_info()

        return [device for device in self.last_results]

    def get_device_name(self, mac):
        """ Returns the name of the given device or None if we don't know """
        try:
            return next(device for device in self.last_results
                        if device == mac)
        except StopIteration:
            return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """ Retrieve the latest information from iCloud
         Returns a bool if scanning is successful
        """

        if not self.success_init:
            return

        with self.lock:
            _LOGGER.info('Scanning iCloud Devices')

            self.last_results = self.get_devices() or {}

    def get_devices(self):
        devices = {}
        for device in self._api.devices:
            try:
                devices[device.status()['name']] = {
                    'device_id': re.sub(r'(\s*|\W*)',
                                        device.status()['name'],
                                        ''),
                    'host_name': device.status()['name'],
                    'gps': (device.location()['latitude'],
                            device.location()['longitude']),
                    'battery': device.status()['batteryLevel']*100
                }
            except TypeError:
                # Device is not tracked.
                continue
        return devices
