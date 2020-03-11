"""Represent the Freebox router and its devices and sensors."""
from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Dict, Optional

from aiofreepybox import Freepybox
from aiofreepybox.api.wifi import Wifi
from aiofreepybox.exceptions import HttpRequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import slugify

from .const import (
    API_VERSION,
    APP_DESC,
    CONNECTION_SENSORS,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class FreeboxRouter:
    """Representation of a Freebox router."""

    def __init__(self, hass: HomeAssistantType, entry: ConfigEntry) -> None:
        """Initialize a Freebox router."""
        self.hass = hass
        self._entry = entry
        self._host = entry.data[CONF_HOST]
        self._port = entry.data[CONF_PORT]

        self._api: Freepybox = None
        self._name = None
        self.mac = None
        self._sw_v = None
        self._attrs = {}

        self.devices: Dict[str, any] = {}
        self.sensors_temperature: Dict[str, int] = {}
        self.sensors_connection: Dict[str, float] = {}

        self.listeners = []

    async def setup(self) -> None:
        """Set up a Freebox router."""
        self._api = await get_api(self.hass, self._host)

        try:
            await self._api.open(self._host, self._port)
        except HttpRequestError:
            _LOGGER.exception("Failed to connect to Freebox")
            return ConfigEntryNotReady

        # System
        fbx_config = await self._api.system.get_config()
        self.mac = fbx_config["mac"]
        self._name = fbx_config["model_info"]["pretty_name"]
        self._sw_v = fbx_config["firmware_version"]

        # Devices & sensors
        await self.update_all()
        async_track_time_interval(self.hass, self.update_all, SCAN_INTERVAL)

    async def update_all(self, now: Optional[datetime] = None) -> None:
        """Update all Freebox platforms."""
        await self.update_sensors()
        await self.update_devices()

    async def update_devices(self) -> None:
        """Update Freebox devices."""
        new_device = False
        fbx_devices: Dict[str, any] = await self._api.lan.get_hosts_list()

        # Adds the Freebox itself
        fbx_devices.append(
            {
                "primary_name": self._name,
                "l2ident": {"id": self.mac},
                "vendor_name": "Freebox SAS",
                "host_type": "router",
                "active": True,
                "attrs": self._attrs,
            }
        )

        for fbx_device in fbx_devices:
            device_mac = fbx_device["l2ident"]["id"]

            if self.devices.get(device_mac) is None:
                new_device = True

            self.devices[device_mac] = fbx_device

        async_dispatcher_send(self.hass, self.signal_device_update)

        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

    async def update_sensors(self) -> None:
        """Update Freebox sensors."""
        # System sensors
        syst_datas: Dict[str, any] = await self._api.system.get_config()

        # According to the doc `syst_datas["sensors"]` is temperature sensors in celsius degree.
        # Name and id of sensors may vary under Freebox devices.
        for sensor in syst_datas["sensors"]:
            self.sensors_temperature[sensor["name"]] = sensor["value"]

        # Connection sensors
        connection_datas: Dict[str, any] = await self._api.connection.get_status()
        for sensor_key in CONNECTION_SENSORS:
            self.sensors_connection[sensor_key] = connection_datas[sensor_key]

        self._attrs = {
            "IPv4": connection_datas.get("ipv4"),
            "IPv6": connection_datas.get("ipv6"),
            "connection_type": connection_datas["media"],
            "uptime": datetime.fromtimestamp(
                round(datetime.now().timestamp()) - syst_datas["uptime_val"]
            ),
            "firmware_version": self._sw_v,
            "serial": syst_datas["serial"],
        }

        async_dispatcher_send(self.hass, self.signal_sensor_update)

    async def reboot(self) -> None:
        """Reboot the Freebox."""
        await self._api.system.reboot()

    async def close(self) -> None:
        """Close the connection."""
        if self._api is not None:
            await self._api.close()
        self._api = None

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self.mac)},
            "identifiers": {(DOMAIN, self.mac)},
            "name": self._name,
            "manufacturer": "Freebox SAS",
            "sw_version": self._sw_v,
        }

    @property
    def signal_device_new(self) -> str:
        """Event specific per Freebox entry to signal new device."""
        return f"{DOMAIN}-{self._host}-device-new"

    @property
    def signal_device_update(self) -> str:
        """Event specific per Freebox entry to signal updates in devices."""
        return f"{DOMAIN}-{self._host}-device-update"

    @property
    def signal_sensor_update(self) -> str:
        """Event specific per Freebox entry to signal updates in sensors."""
        return f"{DOMAIN}-{self._host}-sensor-update"

    @property
    def sensors(self) -> Wifi:
        """Return the wifi."""
        return {**self.sensors_temperature, **self.sensors_connection}

    @property
    def wifi(self) -> Wifi:
        """Return the wifi."""
        return self._api.wifi


async def get_api(hass: HomeAssistantType, host: str) -> Freepybox:
    """Get the Freebox API."""
    freebox_path = Path(hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY).path)
    freebox_path.mkdir(exist_ok=True)

    token_file = Path(f"{freebox_path}/{slugify(host)}.conf")

    return Freepybox(APP_DESC, token_file, API_VERSION)
