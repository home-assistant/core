"""The Open Hardware Monitor component."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.SENSOR]

import logging
_LOGGER = logging.getLogger(__name__)
from .const import *
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util.dt import utcnow

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenHardwareMonitor from a config entry."""

    _LOGGER.warning("Host_main: " + entry.data[CONNECTION_HOST])
    _LOGGER.warning("Port_main: " + entry.data[CONNECTION_PORT])
    data = OpenHardwareMonitorData(entry, hass)
    await data.initialize(utcnow())
    if data.data is None:
        raise PlatformNotReady
    _LOGGER.info("initalized")

    hass.data["monitor_instance"] = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("forwarded everything (awaited)")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    # convert title and unique_id to string
    if config_entry.version == 1:
        if isinstance(config_entry.unique_id, int):
            hass.config_entries.async_update_entry(  # type: ignore[unreachable]
                config_entry,
                unique_id=str(config_entry.unique_id),
                title=str(config_entry.title),
            )

    return True


#import requests
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from aiohttp import *
from aiohttp import web
from aiohttp.hdrs import CONTENT_TYPE, USER_AGENT
from aiohttp.resolver import AsyncResolver
from aiohttp.web_exceptions import HTTPBadGateway, HTTPGatewayTimeout
from homeassistant.util import Throttle
from datetime import timedelta
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)
SCAN_INTERVAL = timedelta(seconds=30)
RETRY_INTERVAL = timedelta(seconds=30)

OHM_VALUE = "Value"
OHM_MIN = "Min"
OHM_MAX = "Max"
OHM_CHILDREN = "Children"
OHM_NAME = "Text"
OHM_ID = "id"
from .const import *
from .sensor import OpenHardwareMonitorDevice
from homeassistant.const import CONF_HOST, CONF_PORT
import json

from homeassistant.helpers import device_registry as dr

class OpenHardwareMonitorData:
    """Class used to pull data from OHM and create sensors."""

    def __init__(self, config_entry, hass):
        """Initialize the Open Hardware Monitor data-handler."""
        self.data = None
        self._config_entry = config_entry
        self._config = config_entry.data
        self._hass = hass
        self.devices = []
        #self.initialize(utcnow())

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Hit by the timer with the configured interval."""
        if self.data is None:
            await self.initialize(utcnow())
        else:
            await self.refresh()

    async def refresh(self):
        """Download and parse JSON from OHM."""
        data_url = (
            f"http://{self._config.get(CONF_HOST)}:"
            f"{self._config.get(CONF_PORT)}/data.json"
        )
        _LOGGER.warning("URL: " + str(data_url))

        #try:
        session = async_get_clientsession(self._hass)
        async with session.get(data_url) as response:
            self.json = await response.text()
        _LOGGER.warning("JSON: " + self.json)

        self.data = json.loads(self.json)

        #response = requests.get(data_url, timeout=30)
        #self.data = response.json()
        #except requests.exceptions.ConnectionError:
        #    _LOGGER.debug("ConnectionError: Is OpenHardwareMonitor running?")

    async def initialize(self, now):
        """Parse of the sensors and adding of devices."""
        await self.refresh()

        if self.data is None:
            return

        self.devices = self.parse_children(self.data, [], [], [])
        
        #async_add_entities(
        #    self.data.devices, True)

    def parse_children(self, json, devices, path, names):
        """Recursively loop through child objects, finding the values."""
        result = devices.copy()

        id = str(json[OHM_ID])
        if id == '1' and self._config.get(GROUP_DEVICES_PER_DEPTH_LEVEL) > 1:
            device_registry = dr.async_get(self._hass)

            host = self._config[CONNECTION_HOST]
            port = self._config[CONNECTION_PORT]
            device_registry.async_get_or_create(
                config_entry_id=self._config_entry.entry_id,
                name=json[OHM_NAME],
                identifiers={(DOMAIN, f"{host}:{port}")},
                #connections={(dr.CONNECTION_NETWORK_MAC, config.mac)},
                manufacturer="Computer",
                #suggested_area="Kitchen",
                #model=config.modelname,
                #model_id=config.modelid,
                #sw_version=config.swversion,
                #hw_version=config.hwversion,
            )

        if json[OHM_CHILDREN]:
            for child_index in range(len(json[OHM_CHILDREN])):
                child_path = path.copy()
                child_path.append(child_index)

                child_names = names.copy()
                if path:
                    child_names.append(json[OHM_NAME])

                obj = json[OHM_CHILDREN][child_index]

                added_devices = self.parse_children(
                    obj, devices, child_path, child_names
                )

                result = result + added_devices
            return result

        if json[OHM_VALUE].find(" ") == -1:
            return result

        unit_of_measurement = json[OHM_VALUE].split(" ")[1]
        child_names = names.copy()
        child_names.append(json[OHM_NAME])
        fullname = " ".join(child_names)

        dev = OpenHardwareMonitorDevice(self, fullname, path, unit_of_measurement, id, child_names, json)

        result.append(dev)
        return result
 