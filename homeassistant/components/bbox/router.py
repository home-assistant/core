"""The Bbox integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import socket
from typing import Any, Callable, TypedDict

import pybbox2
from pybbox2.bbox_api import BboxApiEndpoints
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BboxData(TypedDict):
    """Response from Bbox."""

    current_down_bandwidth: int
    current_down_bandwidth_max: int
    current_up_bandwidth: int
    current_up_bandwidth_max: int
    number_of_reboots: int
    wifi_enabled: bool
    wifi_attrs: dict[str, Any]
    device_info: DeviceInfo


class BboxScannedDevice(TypedDict):
    """Description of scanned device."""

    mac_addr: str
    hostname: str
    ipv4: str | None
    ipv6: list[str] | None
    link: str
    devicetype: str
    active: bool
    last_seen: datetime
    device_info: DeviceInfo


def bbox_request_raising(
    bbox: pybbox2.Bbox, endpoints: tuple[str, str], data: dict | None = None
):
    """Do a Bbox request and raise exceptions on errors."""
    try:
        host = bbox.api_host
        result = bbox.request(*endpoints, data=data)

    except (
        socket.gaierror,
        requests.exceptions.ConnectionError,
        requests.exceptions.SSLError,
    ) as err:
        _LOGGER.error(f"Connection to bbox ({host}) failed ({err}).")
        raise UpdateFailed from err
    except Exception as err:
        if "401" in str(err):
            _LOGGER.error(f"Authentication to bbox ({host}) failed ({err}).")
            raise ConfigEntryAuthFailed from err
        else:
            _LOGGER.error(f"Unknown error while connecting to bbox {err}")
            raise UpdateFailed from err

    if result is False:
        _LOGGER.error(f"Authentication to bbox ({host}) failed.")
        raise ConfigEntryAuthFailed
    return result


class BboxCoordinator(DataUpdateCoordinator[BboxData]):
    """Data update coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=30)
        )
        self._entry = entry
        self.host = self._entry.data[CONF_HOST]

        self.bbox = pybbox2.Bbox(
            api_host=self.host, password=self._entry.data[CONF_PASSWORD]
        )
        # For entities
        self.name = "Bbox"

        self.device_info: DeviceInfo = DeviceInfo()
        self.scanned_devices: dict[str, BboxScannedDevice] = {}

        self.listeners: list[Callable] = []

        self.update_device_info()

    @property
    def entry_id(self) -> str:
        """Return entry ID."""
        return self._entry.entry_id

    @property
    def signal_device_new(self) -> str:
        """Event specific per Freebox entry to signal new device."""
        return f"{DOMAIN}-{self._entry.entry_id}-device-new"

    @property
    def signal_device_update(self) -> str:
        """Event specific per Freebox entry to signal updates in devices."""
        return f"{DOMAIN}-{self._entry.entry_id}-device-update"

    async def update_device_info(self) -> None:
        """Set device info from Bbox requests."""
        box_info = await self.hass.async_add_executor_job(
            bbox_request_raising, self.bbox, BboxApiEndpoints.get_bbox_info
        )
        box_info = box_info["device"]
        lan_info = await self.hass.async_add_executor_job(
            bbox_request_raising, self.bbox, ("get", "v1/lan/ip")
        )
        lan_info = lan_info["lan"]["ip"]

        sw_version = box_info["main"]["version"]
        sw_date = box_info["main"]["date"].split("T")[0]

        self.device_info = DeviceInfo(
            name=self.name,
            connections={(CONNECTION_NETWORK_MAC, lan_info["mac"])},
            identifiers={(DOMAIN, self._entry.entry_id)},
            manufacturer="Bouygues",
            model=box_info["modelname"],
            sw_version=f"{sw_version} ({sw_date})",
            # suggested_area = "",
            # via_device = "",
            # entry_type = "",
            # default_name = "",
            # default_manufacturer = "",
            # default_model = "",
        )

    async def update_hosts_info(self) -> None:
        """Get scanned devices and save in in the class."""
        hosts = await self.hass.async_add_executor_job(
            bbox_request_raising, self.bbox, BboxApiEndpoints.get_all_connected_devices
        )
        scan_time = datetime.now()
        hosts = hosts["hosts"]["list"]

        scanned_devices = {
            host["macaddress"]: BboxScannedDevice(
                mac_addr=host["macaddress"],
                hostname=host["hostname"].strip(),
                ipv4=host["ipaddress"],
                ipv6=[i["ipaddress"] for i in host["ip6address"]],
                link=host["link"],
                devicetype=host["devicetype"],
                active=host["active"],
                last_seen=scan_time - timedelta(seconds=host["lastseen"]),
                device_info=self.device_info,
            )
            for host in hosts
        }

        new_device: bool = False
        for mac, device in scanned_devices.items():
            if mac not in self.scanned_devices:
                new_device = True
            self.scanned_devices[mac] = device

        async_dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

    async def _async_update_data(self) -> BboxData:
        """Get the latest data from the Bbox."""
        await self.update_hosts_info()

        ip_stats = await self.hass.async_add_executor_job(
            bbox_request_raising, self.bbox, BboxApiEndpoints.get_ip_stats
        )
        ip_stats = ip_stats["wan"]["ip"]["stats"]

        box_info = await self.hass.async_add_executor_job(
            bbox_request_raising, self.bbox, BboxApiEndpoints.get_bbox_info
        )
        device_info = box_info["device"]

        wifi_info = await self.hass.async_add_executor_job(
            bbox_request_raising, self.bbox, ("get", "v1/wireless")
        )
        wifi_info = wifi_info["wireless"]["radio"]
        wifi_enabled = (wifi_info["24"]["enable"] + wifi_info["5"]["enable"]) > 0

        data = BboxData(
            current_down_bandwidth=ip_stats["rx"]["bandwidth"],
            current_down_bandwidth_max=ip_stats["rx"]["maxBandwidth"],
            current_up_bandwidth=ip_stats["tx"]["bandwidth"],
            current_up_bandwidth_max=ip_stats["tx"]["maxBandwidth"],
            number_of_reboots=device_info["numberofboots"],
            wifi_enabled=wifi_enabled,
            wifi_attrs={
                "2.4GHz": wifi_info["24"],
                "5GHz": wifi_info["5"],
            },
            device_info=self.device_info,
        )
        return data

    async def set_wifi(self, enable):
        """Set wifi state (both 2.4GHz and 5GHz)."""
        data = {"enable": enable}
        await self.hass.async_add_executor_job(
            bbox_request_raising, self.bbox, ("put", "v1/wireless"), data=data
        )
