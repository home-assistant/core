"""Support for Tado Smart device trackers."""
from __future__ import annotations

import asyncio
from collections import namedtuple
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as BASE_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

from . import TadoConnector
from .const import CONST_OVERLAY_TADO_DEFAULT

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
    return scanner if scanner.success_init else None  # type: ignore [has-type]


Device = namedtuple("Device", ["mac", "name"])


class TadoDeviceScanner(DeviceScanner):
    """Scanner for geofenced devices from Tado."""

    def __init__(self, hass: HomeAssistant, config) -> None:
        """Initialize the scanner."""
        self.hass = hass
        self.last_results: list[str] = []

        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.fallback = CONST_OVERLAY_TADO_DEFAULT

        # The Tado device tracker can work with or without a home_id
        self.home_id = config[CONF_HOME_ID] if CONF_HOME_ID in config else None

        self.tadoconnector = TadoConnector(
            self.hass, self.username, self.password, self.fallback
        )

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
        """Query Tado for device marked as at home.

        Returns boolean if scanning successful.
        """
        _LOGGER.debug("Requesting Tado")
        last_results = []

        await self.hass.async_add_executor_job(self.tadoconnector.setup)
        if self.home_id is None:
            tado_json = await self.hass.async_add_executor_job(self.tadoconnector.getMe)
        else:
            tado_json = await self.hass.async_add_executor_job(
                self.tadoconnector.getMobileDevices
            )

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
