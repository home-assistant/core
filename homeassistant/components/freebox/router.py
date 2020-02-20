"""Represent the Freebox router and its devices and sensors."""
from datetime import datetime, timedelta
import logging
import os
from typing import Dict

from aiofreepybox import Freepybox
from aiofreepybox.api.wifi import Wifi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import slugify

from .const import (
    API_VERSION,
    APP_DESC,
    CONNECTION_SENSORS,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    SENSOR_NAME,
    SENSOR_UPDATE,
    STORAGE_KEY,
    STORAGE_VERSION,
    TEMPERATURE_SENSOR_TEMPLATE,
    TRACKER_UPDATE,
)
from .device_tracker import FreeboxDevice
from .sensor import FreeboxSensor

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

        # Devices
        self._devices: Dict[str, FreeboxDevice] = {}

        # Sensors
        self._temperature_sensors: Dict[str, FreeboxSensor] = {}
        self._connection_sensors: Dict[str, FreeboxSensor] = {}
        self._attrs = {}

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
        if self._api is None:
            return

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
            device_name = fbx_device["primary_name"].strip() or DEFAULT_DEVICE_NAME
            device_mac = fbx_device["l2ident"]["id"]

            if self._devices.get(device_mac) is not None:
                # Seen device -> updating
                _LOGGER.debug("Updating Freebox device: %s", device_name)
                self._devices[device_mac].update_state(fbx_device)
            else:
                # New device, should be unique
                _LOGGER.debug(
                    "Adding Freebox device: %s [MAC: %s]", device_name, device_mac,
                )
                self._devices[device_mac] = FreeboxDevice(fbx_device)

        dispatcher_send(self.hass, TRACKER_UPDATE)

    async def update_sensors(self) -> None:
        """Update Freebox sensors."""
        if self._api is None:
            return

        # System sensors
        syst_datas: Dict[str, any] = await self._api.system.get_config()
        temperature_datas = {item["id"]: item for item in syst_datas["sensors"]}
        # According to the doc it is only temperature sensors in celsius degree.
        # Name and id of the sensors may vary under Freebox devices.

        for sensor_key, sensor_attrs in temperature_datas.items():
            if self._temperature_sensors.get(sensor_key) is not None:
                # Seen sensor -> updating
                _LOGGER.debug("Updating Freebox sensor: %s", sensor_key)
                self._temperature_sensors[sensor_key].update_state(
                    temperature_datas[sensor_key]["value"]
                )
            else:
                # New sensor, should be unique
                _LOGGER.debug("Adding Freebox sensor: %s", sensor_key)
                self._temperature_sensors[sensor_key] = FreeboxSensor(
                    self,
                    {
                        **TEMPERATURE_SENSOR_TEMPLATE,
                        **{
                            SENSOR_NAME: f"Freebox {sensor_attrs['name']}",
                            "value": sensor_attrs["value"],
                        },
                    },
                )
                self._temperature_sensors[sensor_key].update_state(
                    temperature_datas[sensor_key]["value"]
                )

        # Connection sensors
        connection_datas: Dict[str, any] = await self._api.connection.get_status()
        for sensor_key, sensor_attrs in CONNECTION_SENSORS.items():
            if self._connection_sensors.get(sensor_key) is not None:
                # Seen sensor -> updating
                _LOGGER.debug("Updating Freebox sensor: %s", sensor_key)
                self._connection_sensors[sensor_key].update_state(
                    connection_datas[sensor_key]
                )
            else:
                # New sensor, should be unique
                _LOGGER.debug("Adding Freebox sensor: %s", sensor_key)
                self._connection_sensors[sensor_key] = FreeboxSensor(self, sensor_attrs)
                self._connection_sensors[sensor_key].update_state(
                    connection_datas[sensor_key]
                )

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

        dispatcher_send(self.hass, SENSOR_UPDATE)

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
    def wifi(self) -> Wifi:
        """Return the wifi."""
        return self._api.wifi
