"""Support for Tado Smart device trackers."""
from __future__ import annotations

import asyncio
from collections import namedtuple
from datetime import timedelta
from http import HTTPStatus
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as BASE_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_HOME_ID = "home_id"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=30)

PLATFORM_SCHEMA = BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOME_ID): cv.string,
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> TadoDeviceScanner | None:
    """Return a Tado scanner."""
    scanner = TadoDeviceScanner(hass, config[DOMAIN])
    return scanner if scanner.success_init else None


Device = namedtuple("Device", ["mac", "name"])


class TadoDeviceScanner(DeviceScanner):
    """This class gets geofenced devices from Tado."""

    def __init__(self, hass, config):
        """Initialize the scanner."""
        self.hass = hass
        self.last_results = []

        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        # The Tado device tracker can work with or without a home_id
        self.home_id = config[CONF_HOME_ID] if CONF_HOME_ID in config else None

        # If there's a home_id, we need a different API URL
        if self.home_id is None:
            self.tadoapiurl = "https://my.tado.com/api/v2/me"
        else:
            self.tadoapiurl = "https://my.tado.com/api/v2/homes/{home_id}/mobileDevices"

        # The API URL always needs a username and password
        self.tadoapiurl += "?username={username}&password={password}"

        self.websession = None

        self.success_init = asyncio.run_coroutine_threadsafe(
            self._async_update_info(), hass.loop
        ).result()

        _LOGGER.info("Scanner initialized")

    async def async_scan_devices(self):
        """Scan for devices and return a list containing found device ids."""
        await self._async_update_info()
        return [device.mac for device in self.last_results]

    async def async_get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        filter_named = [
            result.name for result in self.last_results if result.mac == device
        ]

        if filter_named:
            return filter_named[0]
        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    async def _async_update_info(self):
        """
        Query Tado for device marked as at home.

        Returns boolean if scanning successful.
        """
        _LOGGER.debug("Requesting Tado")

        if self.websession is None:
            self.websession = async_create_clientsession(
                self.hass, cookie_jar=aiohttp.CookieJar(unsafe=True)
            )

        last_results = []

        try:
            async with async_timeout.timeout(10):
                # Format the URL here, so we can log the template URL if
                # anything goes wrong without exposing username and password.
                url = self.tadoapiurl.format(
                    home_id=self.home_id, username=self.username, password=self.password
                )

                response = await self.websession.get(url)

                if response.status != HTTPStatus.OK:
                    _LOGGER.warning("Error %d on %s", response.status, self.tadoapiurl)
                    return False

                tado_json = await response.json()

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Cannot load Tado data")
            return False

        # Without a home_id, we fetched an URL where the mobile devices can be
        # found under the mobileDevices key.
        if "mobileDevices" in tado_json:
            tado_json = tado_json["mobileDevices"]

        # Find devices that have geofencing enabled, and are currently at home.
        for mobile_device in tado_json:
            if mobile_device.get("location") and mobile_device["location"]["atHome"]:
                device_id = mobile_device["id"]
                device_name = mobile_device["name"]
                last_results.append(Device(device_id, device_name))

        self.last_results = last_results

        _LOGGER.debug(
            "Tado presence query successful, %d device(s) at home",
            len(self.last_results),
        )

        return True
