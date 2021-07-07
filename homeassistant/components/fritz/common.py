"""Support for AVM FRITZ!Box classes."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from types import MappingProxyType
from typing import Any, Callable, TypedDict

from fritzconnection import FritzConnection
from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzConnectionException,
    FritzServiceError,
)
from fritzconnection.lib.fritzhosts import FritzHosts
from fritzconnection.lib.fritzstatus import FritzStatus
from fritzprofiles import FritzProfileSwitch, get_all_profiles

from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    SERVICE_REBOOT,
    SERVICE_RECONNECT,
    TRACKER_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class ClassSetupMissing(Exception):
    """Raised when a Class func is called before setup."""

    def __init__(self) -> None:
        """Init custom exception."""
        super().__init__("Function called before Class setup")


@dataclass
class Device:
    """FRITZ!Box device class."""

    mac: str
    ip_address: str
    name: str


class HostInfo(TypedDict):
    """FRITZ!Box host info class."""

    mac: str
    name: str
    ip: str
    status: bool


class FritzBoxTools:
    """FrtizBoxTools class."""

    def __init__(
        self,
        hass: HomeAssistant,
        password: str,
        username: str = DEFAULT_USERNAME,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        """Initialize FritzboxTools class."""
        self._cancel_scan: CALLBACK_TYPE | None = None
        self._devices: dict[str, Any] = {}
        self._options: MappingProxyType[str, Any] | None = None
        self._unique_id: str | None = None
        self.connection: FritzConnection = None
        self.fritz_hosts: FritzHosts = None
        self.fritz_profiles: dict[str, FritzProfileSwitch] = {}
        self.fritz_status: FritzStatus = None
        self.hass = hass
        self.host = host
        self.password = password
        self.port = port
        self.username = username
        self._mac: str | None = None
        self._model: str | None = None
        self._sw_version: str | None = None

    async def async_setup(self) -> None:
        """Wrap up FritzboxTools class setup."""
        await self.hass.async_add_executor_job(self.setup)

    def setup(self) -> None:
        """Set up FritzboxTools class."""
        self.connection = FritzConnection(
            address=self.host,
            port=self.port,
            user=self.username,
            password=self.password,
            timeout=60.0,
        )

        self.fritz_status = FritzStatus(fc=self.connection)
        info = self.connection.call_action("DeviceInfo:1", "GetInfo")
        if not self._unique_id:
            self._unique_id = info["NewSerialNumber"]

        self._model = info.get("NewModelName")
        self._sw_version = info.get("NewSoftwareVersion")

        self.fritz_profiles = {
            profile: FritzProfileSwitch(
                "http://" + self.host, self.username, self.password, profile
            )
            for profile in get_all_profiles(self.host, self.username, self.password)
        }

    async def async_start(self, options: MappingProxyType[str, Any]) -> None:
        """Start FritzHosts connection."""
        self.fritz_hosts = FritzHosts(fc=self.connection)
        self._options = options
        await self.hass.async_add_executor_job(self.scan_devices)

        self._cancel_scan = async_track_time_interval(
            self.hass, self.scan_devices, timedelta(seconds=TRACKER_SCAN_INTERVAL)
        )

    @callback
    def async_unload(self) -> None:
        """Unload FritzboxTools class."""
        _LOGGER.debug("Unloading FRITZ!Box router integration")
        if self._cancel_scan is not None:
            self._cancel_scan()
            self._cancel_scan = None

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        if not self._unique_id:
            raise ClassSetupMissing()
        return self._unique_id

    @property
    def model(self) -> str:
        """Return device model."""
        if not self._model:
            raise ClassSetupMissing()
        return self._model

    @property
    def sw_version(self) -> str:
        """Return SW version."""
        if not self._sw_version:
            raise ClassSetupMissing()
        return self._sw_version

    @property
    def mac(self) -> str:
        """Return device Mac address."""
        if not self._unique_id:
            raise ClassSetupMissing()
        return self._unique_id

    @property
    def devices(self) -> dict[str, Any]:
        """Return devices."""
        return self._devices

    @property
    def signal_device_new(self) -> str:
        """Event specific per FRITZ!Box entry to signal new device."""
        return f"{DOMAIN}-device-new-{self._unique_id}"

    @property
    def signal_device_update(self) -> str:
        """Event specific per FRITZ!Box entry to signal updates in devices."""
        return f"{DOMAIN}-device-update-{self._unique_id}"

    def _update_info(self) -> list[HostInfo]:
        """Retrieve latest information from the FRITZ!Box."""
        return self.fritz_hosts.get_hosts_info()

    def scan_devices(self, now: datetime | None = None) -> None:
        """Scan for new devices and return a list of found device ids."""
        _LOGGER.debug("Checking devices for FRITZ!Box router %s", self.host)

        _default_consider_home = DEFAULT_CONSIDER_HOME.total_seconds()
        if self._options:
            consider_home = self._options.get(
                CONF_CONSIDER_HOME, _default_consider_home
            )
        else:
            consider_home = _default_consider_home

        new_device = False
        for known_host in self._update_info():
            if not known_host.get("mac"):
                continue

            dev_mac = known_host["mac"]
            dev_name = known_host["name"]
            dev_ip = known_host["ip"]
            dev_home = known_host["status"]

            dev_info = Device(dev_mac, dev_ip, dev_name)

            if dev_mac in self._devices:
                self._devices[dev_mac].update(dev_info, dev_home, consider_home)
            else:
                device = FritzDevice(dev_mac, dev_name)
                device.update(dev_info, dev_home, consider_home)
                self._devices[dev_mac] = device
                new_device = True

        dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            dispatcher_send(self.hass, self.signal_device_new)

    async def service_fritzbox(self, service: str) -> None:
        """Define FRITZ!Box services."""
        _LOGGER.debug("FRITZ!Box router: %s", service)

        if not self.connection:
            raise HomeAssistantError("Unable to establish a connection")

        try:
            if service == SERVICE_REBOOT:
                await self.hass.async_add_executor_job(
                    self.connection.call_action, "DeviceConfig1", "Reboot"
                )
            elif service == SERVICE_RECONNECT:
                await self.hass.async_add_executor_job(
                    self.connection.call_action,
                    "WANIPConn1",
                    "ForceTermination",
                )
        except (FritzServiceError, FritzActionError) as ex:
            raise HomeAssistantError("Service or parameter unknown") from ex
        except FritzConnectionException as ex:
            raise HomeAssistantError("Service not supported") from ex


@dataclass
class FritzData:
    """Storage class for platform global data."""

    tracked: dict = field(default_factory=dict)


class FritzDevice:
    """FritzScanner device."""

    def __init__(self, mac: str, name: str) -> None:
        """Initialize device info."""
        self._mac = mac
        self._name = name
        self._ip_address: str | None = None
        self._last_activity: datetime | None = None
        self._connected = False

    def update(self, dev_info: Device, dev_home: bool, consider_home: float) -> None:
        """Update device info."""
        utc_point_in_time = dt_util.utcnow()

        if self._last_activity:
            consider_home_evaluated = (
                utc_point_in_time - self._last_activity
            ).total_seconds() < consider_home
        else:
            consider_home_evaluated = dev_home

        if not self._name:
            self._name = dev_info.name or self._mac.replace(":", "_")

        self._connected = dev_home or consider_home_evaluated

        if dev_home:
            self._last_activity = utc_point_in_time

        self._ip_address = dev_info.ip_address if self._connected else None

    @property
    def is_connected(self) -> bool:
        """Return connected status."""
        return self._connected

    @property
    def mac_address(self) -> str:
        """Get MAC address."""
        return self._mac

    @property
    def hostname(self) -> str:
        """Get Name."""
        return self._name

    @property
    def ip_address(self) -> str | None:
        """Get IP address."""
        return self._ip_address

    @property
    def last_activity(self) -> datetime | None:
        """Return device last activity."""
        return self._last_activity


class SwitchInfo(TypedDict):
    """FRITZ!Box switch info class."""

    description: str
    friendly_name: str
    icon: str
    type: str
    callback_update: Callable
    callback_switch: Callable


class FritzBoxBaseEntity:
    """Fritz host entity base class."""

    def __init__(self, fritzbox_tools: FritzBoxTools, device_name: str) -> None:
        """Init device info class."""
        self._fritzbox_tools = fritzbox_tools
        self._device_name = device_name

    @property
    def mac_address(self) -> str:
        """Return the mac address of the main device."""
        return self._fritzbox_tools.mac

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""

        return {
            "connections": {(CONNECTION_NETWORK_MAC, self.mac_address)},
            "identifiers": {(DOMAIN, self._fritzbox_tools.unique_id)},
            "name": self._device_name,
            "manufacturer": "AVM",
            "model": self._fritzbox_tools.model,
            "sw_version": self._fritzbox_tools.sw_version,
        }
