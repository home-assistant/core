"""
Support for French FAI Bouygues Bbox routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.bbox/
"""
from collections import namedtuple
import logging
from datetime import timedelta

import homeassistant.util.dt as dt_util
from homeassistant.components.device_tracker import DOMAIN, DeviceScanner
from homeassistant.util import Throttle

REQUIREMENTS = ['pybbox==0.0.5-alpha']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=60)


def get_scanner(hass, config):
    """Validate the configuration and return a Bbox scanner."""
    scanner = BboxDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


Device = namedtuple('Device', ['mac', 'name', 'ip', 'last_update'])


class BboxDeviceScanner(DeviceScanner):
    """This class scans for devices connected to the bbox."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.last_results = []  # type: List[Device]

        self.success_init = self._update_info()
        _LOGGER.info("Scanner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device.mac for device in self.last_results]

    def get_device_name(self, mac):
        """Return the name of the given device or None if we don't know."""
        filter_named = [device.name for device in self.last_results if
                        device.mac == mac]

        if filter_named:
            return filter_named[0]
        else:
            return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Check the Bbox for devices.

        Returns boolean if scanning successful.
        """
        _LOGGER.info("Scanning...")

        import pybbox

        box = pybbox.Bbox()
        result = box.get_all_connected_devices()

        now = dt_util.now()
        last_results = []
        for device in result:
            if device['active'] != 1:
                continue
            last_results.append(
                Device(device['macaddress'], device['hostname'],
                       device['ipaddress'], now))

        self.last_results = last_results

        _LOGGER.info("Scan successful")
        return True
