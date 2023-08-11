"""Represent the Freebox router and its devices and sensors."""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from datetime import datetime
import logging
import os
from pathlib import Path
from typing import Any

from freebox_api import Freepybox
from freebox_api.api.call import Call
from freebox_api.api.home import Home
from freebox_api.api.wifi import Wifi
from freebox_api.exceptions import HttpRequestError, NotOpenError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify

from .const import (
    API_VERSION,
    APP_DESC,
    CONNECTION_SENSORS_KEYS,
    DOMAIN,
    HOME_COMPATIBLE_PLATFORMS,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


async def get_api(hass: HomeAssistant, host: str) -> Freepybox:
    """Get the Freebox API."""
    freebox_path = Store(hass, STORAGE_VERSION, STORAGE_KEY).path

    if not os.path.exists(freebox_path):
        await hass.async_add_executor_job(os.makedirs, freebox_path)

    token_file = Path(f"{freebox_path}/{slugify(host)}.conf")

    return Freepybox(APP_DESC, token_file, API_VERSION)


class FreeboxRouter:
    """Representation of a Freebox router."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: Freepybox,
        freebox_config: Mapping[str, Any],
    ) -> None:
        """Initialize a Freebox router."""
        self.hass = hass
        self._host = entry.data[CONF_HOST]
        self._port = entry.data[CONF_PORT]

        self._api: Freepybox = api
        self.name: str = freebox_config["model_info"]["pretty_name"]
        self.mac: str = freebox_config["mac"]
        self._sw_v: str = freebox_config["firmware_version"]
        self._attrs: dict[str, Any] = {}

        self.devices: dict[str, dict[str, Any]] = {}
        self.disks: dict[int, dict[str, Any]] = {}
        self.raids: dict[int, dict[str, Any]] = {}
        self.sensors_temperature: dict[str, int] = {}
        self.sensors_connection: dict[str, float] = {}
        self.call_list: list[dict[str, Any]] = []
        self.home_granted = True
        self.home_devices: dict[str, Any] = {}
        self.listeners: list[dict[str, Any]] = []

    async def update_all(self, now: datetime | None = None) -> None:
        """Update all Freebox platforms."""
        await self.update_device_trackers()
        await self.update_sensors()
        await self.update_home_devices()

    async def update_device_trackers(self) -> None:
        """Update Freebox devices."""
        new_device = False
        fbx_devices: list[dict[str, Any]] = await self._api.lan.get_hosts_list()

        # Adds the Freebox itself
        fbx_devices.append(
            {
                "primary_name": self.name,
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
        syst_datas: dict[str, Any] = await self._api.system.get_config()

        # According to the doc `syst_datas["sensors"]` is temperature sensors in celsius degree.
        # Name and id of sensors may vary under Freebox devices.
        for sensor in syst_datas["sensors"]:
            self.sensors_temperature[sensor["name"]] = sensor.get("value")

        # Connection sensors
        connection_datas: dict[str, Any] = await self._api.connection.get_status()
        for sensor_key in CONNECTION_SENSORS_KEYS:
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

        self.call_list = await self._api.call.get_calls_log()

        await self._update_disks_sensors()

        await self._update_raids_sensors()

        async_dispatcher_send(self.hass, self.signal_sensor_update)

    async def _update_disks_sensors(self) -> None:
        """Update Freebox disks."""
        # None at first request
        fbx_disks: list[dict[str, Any]] = await self._api.storage.get_disks() or []

        for fbx_disk in fbx_disks:
            self.disks[fbx_disk["id"]] = fbx_disk

    async def _update_raids_sensors(self) -> None:
        """Update Freebox raids."""
        # None at first request
        try:
            fbx_raids: list[dict[str, Any]] = await self._api.storage.get_raids() or []
        except HttpRequestError:
            _LOGGER.warning("Unable to enumerate raid disks")
        else:
            for fbx_raid in fbx_raids:
                self.raids[fbx_raid["id"]] = fbx_raid

    async def update_home_devices(self) -> None:
        """Update Home devices (alarm, light, sensor, switch, remote ...)."""
        if not self.home_granted:
            return

        try:
            home_nodes: list[Any] = await self.home.get_home_nodes() or []
        except HttpRequestError:
            self.home_granted = False
            _LOGGER.warning("Home access is not granted")
            return

        new_device = False
        for home_node in home_nodes:
            if home_node["category"] in HOME_COMPATIBLE_PLATFORMS:
                if self.home_devices.get(home_node["id"]) is None:
                    new_device = True
                self.home_devices[home_node["id"]] = home_node

        async_dispatcher_send(self.hass, self.signal_home_device_update)

        if new_device:
            async_dispatcher_send(self.hass, self.signal_home_device_new)

    async def reboot(self) -> None:
        """Reboot the Freebox."""
        await self._api.system.reboot()

    async def close(self) -> None:
        """Close the connection."""
        with suppress(NotOpenError):
            await self._api.close()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            configuration_url=f"https://{self._host}:{self._port}/",
            connections={(CONNECTION_NETWORK_MAC, self.mac)},
            identifiers={(DOMAIN, self.mac)},
            manufacturer="Freebox SAS",
            name=self.name,
            sw_version=self._sw_v,
        )

    @property
    def signal_device_new(self) -> str:
        """Event specific per Freebox entry to signal new device."""
        return f"{DOMAIN}-{self._host}-device-new"

    @property
    def signal_home_device_new(self) -> str:
        """Event specific per Freebox entry to signal new home device."""
        return f"{DOMAIN}-{self._host}-home-device-new"

    @property
    def signal_device_update(self) -> str:
        """Event specific per Freebox entry to signal updates in devices."""
        return f"{DOMAIN}-{self._host}-device-update"

    @property
    def signal_sensor_update(self) -> str:
        """Event specific per Freebox entry to signal updates in sensors."""
        return f"{DOMAIN}-{self._host}-sensor-update"

    @property
    def signal_home_device_update(self) -> str:
        """Event specific per Freebox entry to signal update in home devices."""
        return f"{DOMAIN}-{self._host}-home-device-update"

    @property
    def sensors(self) -> dict[str, Any]:
        """Return sensors."""
        return {**self.sensors_temperature, **self.sensors_connection}

    @property
    def call(self) -> Call:
        """Return the call."""
        return self._api.call

    @property
    def wifi(self) -> Wifi:
        """Return the wifi."""
        return self._api.wifi

    @property
    def home(self) -> Home:
        """Return the home."""
        return self._api.home
