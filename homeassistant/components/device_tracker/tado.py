"""
Support for Tado Smart Thermostat.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.tado/
"""
import logging
from datetime import timedelta
from collections import namedtuple

import asyncio
import aiohttp
import async_timeout

import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.helpers.aiohttp_client import async_create_clientsession

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string
})


def get_scanner(hass, config):
    """Return a Tado scanner."""
    scanner = TadoDeviceScanner(hass, config[DOMAIN])

    return scanner if scanner.success_init else None


Device = namedtuple("Device", ["mac", "name"])


class TadoDeviceScanner(DeviceScanner):
    """This class gets geofenced devices from Tado."""

    def __init__(self, hass, config):
        """Initialize the scanner."""
        self.last_results = []

        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.tadoapiurl = 'https://my.tado.com/api/v2/me' \
                          '?username={}&password={}'

        self.websession = async_create_clientsession(
            hass, cookie_jar=aiohttp.CookieJar(unsafe=True, loop=hass.loop))

        self.success_init = self._update_info()
        _LOGGER.info("Tado scanner initialized")

    @asyncio.coroutine
    def async_scan_devices(self):
        """Scan for devices and return a list containing found device ids."""
        yield from self._update_info()

        return [device.mac for device in self.last_results]

    @asyncio.coroutine
    def async_get_device_name(self, mac):
        """Return the name of the given device or None if we don't know."""
        filter_named = [device.name for device in self.last_results
                        if device.mac == mac]

        if filter_named:
            return filter_named[0]
        else:
            return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """
        Query Tado for device marked as at home.

        Returns boolean if scanning successful.
        """
        _LOGGER.debug("Requesting Tado")

        last_results = []

        response = None
        tadojson = None
        try:
            # get first token
            with async_timeout.timeout(10, loop=self.hass.loop):
                url = self.tadoapiurl.format(self.username, self.password)
                response = yield from self.websession.get(
                    url
                )

                # error on Tado webservice
                if response.status != 200:
                    _LOGGER.warning(
                        "Error %d on %s.", response.status, self.tadoapiurl)
                    self.token = None
                    return

                tadojson = yield from response.json()

        except (asyncio.TimeoutError, aiohttp.errors.ClientError):
            _LOGGER.error("Can not load Tado data")
            return False

        finally:
            if response is not None:
                yield from response.release()

        # Find devices that have geofencing enabled, and are currently at home
        for mobiledevice in tadojson['mobileDevices']:
            if 'location' in mobiledevice:
                if mobiledevice['location']['atHome']:
                    deviceid = mobiledevice['id']
                    devicename = mobiledevice['name']
                    last_results.append(Device(deviceid, devicename))

        self.last_results = last_results

        _LOGGER.info("Tado presence query successful")
        return True
