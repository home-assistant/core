"""Support for French FAI Bouygues Bbox routers."""
from __future__ import annotations

from collections import namedtuple
from datetime import timedelta
import logging

import pybbox
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "192.168.1.254"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string}
)


def get_scanner(hass, config):
    """Validate the configuration and return a Bbox scanner."""
    scanner = BboxDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


Device = namedtuple("Device", ["mac", "name", "ip", "last_update"])


class BboxDeviceScanner(DeviceScanner):
    """This class scans for devices connected to the bbox."""

    def __init__(self, config):
        """Get host from config."""

        self.host = config[CONF_HOST]

        """Initialize the scanner."""
        self.last_results: list[Device] = []

        self.success_init = self._update_info()
        _LOGGER.info("Scanner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device.mac for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        filter_named = [
            result.name for result in self.last_results if result.mac == device
        ]

        if filter_named:
            return filter_named[0]
        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Check the Bbox for devices.

        Returns boolean if scanning successful.
        """
        _LOGGER.info("Scanning")

        box = pybbox.Bbox(ip=self.host)
        result = box.get_all_connected_devices()

        now = dt_util.now()
        last_results = []
        for device in result:
            if device["active"] != 1:
                continue
            last_results.append(
                Device(
                    device["macaddress"], device["hostname"], device["ipaddress"], now
                )
            )

        self.last_results = last_results

        _LOGGER.info("Scan successful")
        return True
