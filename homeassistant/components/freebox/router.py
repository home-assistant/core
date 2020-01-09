"""Represent the Freebox router and its devices and sensors."""
from datetime import datetime, timedelta
import logging
from typing import Dict

from aiofreepybox import Freepybox
from aiofreepybox.api.wifi import Wifi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    API_VERSION,
    APP_DESC,
    CONN_SENSORS,
    DOMAIN,
    SENSOR_DEVICE_CLASS,
    SENSOR_ICON,
    SENSOR_NAME,
    SENSOR_UNIT,
    SENSOR_UPDATE,
    TEMP_SENSOR_TEMPLATE,
    TRACKER_UPDATE,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class FreeboxRouter:
    """Representation of a Freebox router."""

    def __init__(self, hass: HomeAssistantType, entry: ConfigEntry, token_file: str):
        """Initialize a Freebox router."""
        self.hass = hass
        self._entry = entry
        self._host = entry.data[CONF_HOST]
        self._port = entry.data[CONF_PORT]
        self._token_file = token_file

        self._api: Freepybox = None
        self._name = None
        self._mac = None
        self._sw_v = None

        # Devices
        self._devices: Dict[str, FreeboxDevice] = {}

        # Sensors
        self._temp_sensors: Dict[str, FreeboxSensor] = {}
        self._conn_sensors: Dict[str, FreeboxSensor] = {}

    async def setup(self) -> None:
        """Set up a Freebox router."""
        self._api = Freepybox(APP_DESC, self._token_file, API_VERSION)

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
        await self.update_devices()
        await self.update_sensors()

    async def update_devices(self) -> None:
        """Update Freebox devices."""
        if self._api is None:
            return

        fbx_devices: Dict[str, any] = await self._api.lan.get_hosts_list()
        for fbx_device in fbx_devices:
            device_name = fbx_device["primary_name"]
            device_mac = fbx_device["l2ident"]["id"]

            if self._devices.get(device_mac) is not None:
                # Seen device -> updating
                _LOGGER.debug("Updating Freebox device: %s", device_name)
                self._devices[device_mac].update(fbx_device)
            else:
                # New device, should be unique
                _LOGGER.debug(
                    "Adding Freebox device: %s [MAC: %s]", device_name, device_mac,
                )
                self._devices[device_mac] = FreeboxDevice(fbx_device)
                self._devices[device_mac].update(fbx_device)

        dispatcher_send(self.hass, TRACKER_UPDATE)

    async def update_sensors(self) -> None:
        """Update Freebox sensors."""
        if self._api is None:
            return

        # System sensors
        syst_datas: Dict[str, any] = await self._api.system.get_config()
        temp_datas = {item["id"]: item for item in syst_datas["sensors"]}
        # According to the doc it is only temperature sensors in celsius degree, name and id of the sensors may vary under Freebox devices

        for sensor_key, sensor_attrs in temp_datas.items():

            if self._temp_sensors.get(sensor_key) is not None:
                # Seen sensor -> updating
                _LOGGER.debug("Updating Freebox sensor: %s", sensor_key)
                self._temp_sensors[sensor_key].update(temp_datas[sensor_key]["value"])
            else:
                # New sensor, should be unique
                _LOGGER.debug("Adding Freebox sensor: %s", sensor_key)
                self._temp_sensors[sensor_key] = FreeboxSensor(
                    {
                        **TEMP_SENSOR_TEMPLATE,
                        **{
                            SENSOR_NAME: f"Freebox {sensor_attrs['name']}",
                            "value": sensor_attrs["value"],
                        },
                    }
                )
                self._temp_sensors[sensor_key].update(temp_datas[sensor_key]["value"])

        # Connection sensors
        conn_datas: Dict[str, any] = await self._api.connection.get_status()
        for sensor_key, sensor_attrs in CONN_SENSORS.items():
            if self._conn_sensors.get(sensor_key) is not None:
                # Seen sensor -> updating
                _LOGGER.debug("Updating Freebox sensor: %s", sensor_key)
                self._conn_sensors[sensor_key].update(conn_datas[sensor_key])
            else:
                # New sensor, should be unique
                _LOGGER.debug("Adding Freebox sensor: %s", sensor_key)
                self._conn_sensors[sensor_key] = FreeboxSensor(sensor_attrs)
                self._conn_sensors[sensor_key].update(conn_datas[sensor_key])

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
    def mac(self) -> str:
        """Return the router MAC address."""
        return self._mac

    @property
    def firmware_version(self) -> str:
        """Return the router sofware version."""
        return self._sw_v

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self.mac)},
            "identifiers": {(DOMAIN, self.mac)},
            "name": self.name,
            "manufacturer": "Freebox SAS",
            "sw_version": self.firmware_version,
        }

    @property
    def devices(self) -> Dict[str, any]:
        """Return all devices."""
        return self._devices

    @property
    def sensors(self) -> Dict[str, any]:
        """Return all sensors."""
        return {**self._temp_sensors, **self._conn_sensors}

    @property
    def wifi(self) -> Wifi:
        """Return the wifi."""
        return self._api.wifi


class FreeboxDevice:
    """Representation of a Freebox device."""

    def __init__(self, device: Dict[str, any]):
        """Initialize a Freebox device."""
        self._name = device["primary_name"]
        self._mac = device["l2ident"]["id"]
        self._manufacturer = device["vendor_name"]
        self._icon = icon_for_freebox_device(device)

        self._active = device["active"]
        self._reachable = device["reachable"]
        self._attrs = {
            "reachable": self._reachable,
            "last_time_reachable": datetime.fromtimestamp(
                device["last_time_reachable"]
            ),
            "last_time_activity": datetime.fromtimestamp(device["last_activity"]),
        }

    def update(self, device: Dict[str, any]) -> None:
        """Update the Freebox device."""
        self._active = device["active"]
        self._reachable = device["reachable"]
        self._attrs = {
            "reachable": self._reachable,
            "last_time_reachable": datetime.fromtimestamp(
                device["last_time_reachable"]
            ),
            "last_time_activity": datetime.fromtimestamp(device["last_activity"]),
        }

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def mac(self) -> str:
        """Return the MAC address."""
        return self._mac

    @property
    def manufacturer(self) -> str:
        """Return the manufacturer."""
        return self._manufacturer

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def active(self) -> bool:
        """Return true if the host sends traffic to the Freebox."""
        return self._active

    @property
    def reachable(self) -> bool:
        """Return true if the host can receive traffic from the Freebox."""
        return self._reachable

    @property
    def state_attributes(self) -> Dict[str, any]:
        """Return the attributes."""
        return self._attrs


class FreeboxSensor:
    """Representation of a Freebox sensor."""

    def __init__(self, sensor: Dict[str, any]):
        """Initialize a Freebox sensor."""
        self._state = None
        self._name = sensor[SENSOR_NAME]
        self._unit = sensor[SENSOR_UNIT]
        self._icon = sensor[SENSOR_ICON]
        self._device_class = sensor[SENSOR_DEVICE_CLASS]

    def update(self, state: any) -> None:
        """Update the Freebox sensor."""
        if self._unit == "KB/s":
            self._state = round(state / 1000, 2)
        else:
            self._state = state

    @property
    def state(self) -> str:
        """Return the state."""
        return self._state

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def unit(self) -> str:
        """Return the unit."""
        return self._unit

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def device_class(self) -> str:
        """Return the device_class."""
        return self._device_class


def icon_for_freebox_device(device) -> str:
    """Return a host icon from his type."""
    switcher = {
        "freebox_delta": "mdi:television-guide",
        "freebox_hd": "mdi:television-guide",
        "freebox_mini": "mdi:television-guide",
        "freebox_player": "mdi:television-guide",
        "ip_camera": "mdi:cctv",
        "ip_phone": "mdi:phone-voip",
        "laptop": "mdi:laptop",
        "multimedia_device": "mdi:play-network",
        "nas": "mdi:nas",
        "networking_device": "mdi:network",
        "printer": "mdi:printer",
        "smartphone": "mdi:cellphone",
        "tablet": "mdi:tablet",
        "television": "mdi:television",
        "vg_console": "mdi:gamepad-variant",
        "workstation": "mdi:desktop-tower-monitor",
    }

    return switcher.get(device["host_type"], "mdi:help-network")
