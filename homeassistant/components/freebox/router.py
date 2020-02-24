"""Represent the Freebox router and its devices and sensors."""
from datetime import datetime, timedelta
import logging
import os
from typing import Dict

from aiofreepybox import Freepybox
from aiofreepybox.api.system import System
from aiofreepybox.api.wifi import Wifi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
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

    def __init__(self, hass: HomeAssistantType, entry: ConfigEntry):
        """Initialize a Freebox router."""
        self.hass = hass
        self._entry = entry
        self._host = entry.data[CONF_HOST]
        self._port = entry.data[CONF_PORT]

        self._api: Freepybox = None
        self._name = None
        self._mac = None
        self._sw_v = None
        self._attrs = {}

        # Devices
        self._devices: Dict[str, any] = {}

        # Sensors
        self._temperature_sensors: Dict[str, any] = {}
        self._connection_sensors: Dict[str, any] = {}

        self.listeners = []

    async def setup(self) -> None:
        """Set up a Freebox router."""
        freebox_dir = self.hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

        if not os.path.exists(freebox_dir.path):
            await self.hass.async_add_executor_job(os.makedirs, freebox_dir.path)

        token_file = self.hass.config.path(
            f"{freebox_dir.path}/{slugify(self._host)}.conf"
        )

        self._api = Freepybox(APP_DESC, token_file, API_VERSION)

        await self._api.open(self._host, self._port)

        # System
        fbx_config = await self._api.system.get_config()
        self._mac = fbx_config["mac"]
        self._name = fbx_config["model_info"]["pretty_name"]
        self._sw_v = fbx_config["firmware_version"]

        # Devices & sensors
        await self.update_all()
        async_track_time_interval(self.hass, self.update_all, SCAN_INTERVAL)

    async def update_all(self, now=None) -> None:
        """Update all Freebox platforms."""
        await self.update_sensors()
        await self.update_devices()

    async def update_devices(self) -> None:
        """Update Freebox devices."""
        _LOGGER.warning("ROUTER_UPDATE_DEVICES")
        new_device = False
        fbx_devices: Dict[str, any] = await self._api.lan.get_hosts_list()

        # Adds the Freebox itself
        fbx_devices.append(
            {
                "primary_name": self.name,
                "l2ident": {"id": self.mac},
                "vendor_name": self.manufacturer,
                "host_type": "router",
                "active": True,
                "attrs": self._attrs,
            }
        )

        for fbx_device in fbx_devices:
            device_mac = fbx_device["l2ident"]["id"]
            self._devices[device_mac] = fbx_device

            if self._devices.get(device_mac) is None:
                new_device = True

        async_dispatcher_send(self.hass, self.signal_device_update)

        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

    async def update_sensors(self) -> None:
        """Update Freebox sensors."""
        _LOGGER.warning("ROUTER_UPDATE_SENSORS")

        # System sensors
        syst_datas: Dict[str, any] = await self._api.system.get_config()
        temperature_datas = {item["id"]: item for item in syst_datas["sensors"]}
        # According to the doc it is only temperature sensors in celsius degree.
        # Name and id of the sensors may vary under Freebox devices.

        for sensor_key, sensor_attrs in temperature_datas.items():
            self._temperature_sensors[sensor_key] = sensor_attrs["value"]

        # Connection sensors
        connection_datas: Dict[str, any] = await self._api.connection.get_status()
        for sensor_key, sensor_attrs in CONNECTION_SENSORS.items():
            self._connection_sensors[sensor_key] = connection_datas[sensor_key]

        self._attrs = {
            "IPv4": connection_datas.get("ipv4"),
            "IPv6": connection_datas.get("ipv6"),
            "connection_type": connection_datas["media"],
            "uptime": datetime.fromtimestamp(
                round(datetime.now().timestamp()) - syst_datas["uptime_val"]
            ),
            "firmware_version": self.firmware_version,
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
    def name(self) -> str:
        """Return the router name."""
        return self._name

    @property
    def manufacturer(self) -> str:
        """Return the router manufacturer."""
        return "Freebox SAS"

    @property
    def mac(self) -> str:
        """Return the router MAC address."""
        return self._mac

    @property
    def firmware_version(self) -> str:
        """Return the router software version."""
        return self._sw_v

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self.mac)},
            "identifiers": {(DOMAIN, self.mac)},
            "name": self.name,
            "manufacturer": self.manufacturer,
            "sw_version": self.firmware_version,
        }

    @property
    def devices(self) -> Dict[str, any]:
        """Return all devices."""
        return self._devices

    @property
    def sensors(self) -> Dict[str, any]:
        """Return all sensors."""
        return {**self._temperature_sensors, **self._connection_sensors}

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
    def system(self) -> System:
        """Return the system."""
        return self._api.system

    @property
    def wifi(self) -> Wifi:
        """Return the wifi."""
        return self._api.wifi
