"""Support for French FAI Bouygues Bbox routers."""

from asyncio import run_coroutine_threadsafe
from collections import namedtuple
from datetime import timedelta
import logging
from typing import override

import probatio

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle, dt as dt_util

from .api import BboxApi, BboxError
from .const import DEFAULT_HOST

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=60)

REQUEST_TIMEOUT = 10  # seconds

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        probatio.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        # The hosts list requires an authenticated session on recent
        # firmwares.
        probatio.Required(CONF_PASSWORD): cv.string,
        # The scanner fetches at most once per MIN_TIME_BETWEEN_SCANS; the
        # legacy platform default of SCAN_INTERVAL (12s) would just redo
        # the same cached scan.
        probatio.Optional(CONF_SCAN_INTERVAL, default=MIN_TIME_BETWEEN_SCANS): (
            cv.time_period
        ),
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> BboxDeviceScanner | None:
    """Validate the configuration and return a Bbox scanner."""
    domain_config = config[DEVICE_TRACKER_DOMAIN]
    scanner = BboxDeviceScanner(
        hass, domain_config[CONF_HOST], domain_config[CONF_PASSWORD]
    )

    return scanner if scanner.success_init else None


Device = namedtuple("Device", ["mac", "name", "ip", "last_update"])  # noqa: PYI024


class BboxDeviceScanner(DeviceScanner):
    """Scanner for devices connected to the bbox."""

    def __init__(self, hass: HomeAssistant, host: str, password: str) -> None:
        """Initialize the scanner."""
        self.hass = hass
        self._host = host
        self._password = password
        self._api: BboxApi | None = None
        self.last_results: list[Device] = []

        self.success_init = self._update_info()

    async def _async_fetch(self):
        """Fetch the connected devices from the event loop.

        The session and the api client must be created on the event loop:
        this method only runs there, through the bridge in
        :meth:`_update_info`.
        """
        if self._api is None:
            self._api = BboxApi(
                async_get_clientsession(self.hass), self._password, self._host
            )
        return await self._api.get_connected_devices()

    @override
    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device.mac for device in self.last_results]

    @override
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
        _LOGGER.debug("Scanning")

        try:
            result = run_coroutine_threadsafe(
                self._async_fetch(), self.hass.loop
            ).result(REQUEST_TIMEOUT)
        except (BboxError, TimeoutError) as error:
            _LOGGER.error("Error fetching Bbox device list: %s", error)
            self.last_results = []
            return False

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

        _LOGGER.debug("Scan successful")
        return True
