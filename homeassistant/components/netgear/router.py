"""Represent the Netgear router and its devices."""

from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
import logging
from typing import Any

from aiohttp import CookieJar
from netgearpy import NetgearClient
from netgearpy.models import (
    AttachedDevice,
    DeviceInfo,
    DeviceMode,
    SystemInfo,
    TrafficMeterStatistics,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.util import dt as dt_util
from homeassistant.util.ssl import SSLCipherList

from .const import CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME, DOMAIN, MODELS_V2

_LOGGER = logging.getLogger(__name__)


class NetgearRouter:
    """Representation of a Netgear router."""

    _info: DeviceInfo
    api: NetgearClient

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize a Netgear router."""
        assert entry.unique_id
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id
        self.unique_id = entry.unique_id
        self._host: str = entry.data[CONF_HOST]
        self._port: int = entry.data[CONF_PORT]
        self._ssl: bool = entry.data[CONF_SSL]
        self._username: str = entry.data[CONF_USERNAME]
        self._password: str = entry.data[CONF_PASSWORD]

        self.model = ""
        self.mode = DeviceMode.ROUTER
        self.device_name = ""
        self.firmware_version = ""
        self.hardware_version = ""
        self.serial_number = ""

        self.track_devices = True
        self.method_version = 1
        consider_home_int = entry.options.get(
            CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
        )
        self._consider_home = timedelta(seconds=consider_home_int)

        self.devices: dict[str, dict[str, Any]] = {}

    async def _setup(self) -> bool:
        """Set up a Netgear router sync portion."""
        self.api = NetgearClient(
            self._host,
            async_create_clientsession(
                self.hass,
                ssl_cipher=SSLCipherList.INSECURE,
                verify_ssl=False,
                cookie_jar=CookieJar(unsafe=True),
            ),
        )
        await self.api.login(self._username, self._password)

        self._info = await self.api.get_device_info()

        self.device_name = self._info.device_name
        self.model = self._info.model
        self.firmware_version = self._info.firmware_version
        self.hardware_version = self._info.hardware_version
        self.serial_number = self._info.serial_number
        self.mode = self._info.device_mode

        enabled_entries = [
            entry
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.disabled_by is None
        ]
        self.track_devices = self.mode == DeviceMode.ROUTER or len(enabled_entries) == 1
        _LOGGER.debug(
            "Netgear track_devices = '%s', device mode '%s'",
            self.track_devices,
            self.mode,
        )

        for model in MODELS_V2:
            if self.model.startswith(model):
                self.method_version = 2

        # if self.method_version == 2 and self.track_devices:
        #     if not self.api.get_attached_devices_2():
        #         _LOGGER.error(
        #             (
        #                 "Netgear Model '%s' in MODELS_V2 list, but failed to get"
        #                 " attached devices using V2"
        #             ),
        #             self.model,
        #         )
        #         self.method_version = 1

        return True

    async def async_setup(self) -> bool:
        """Set up a Netgear router."""
        await self._setup()

        # set already known devices to away instead of unavailable
        if self.track_devices:
            device_registry = dr.async_get(self.hass)
            devices = dr.async_entries_for_config_entry(device_registry, self.entry_id)
            for device_entry in devices:
                if device_entry.via_device_id is None:
                    continue  # do not add the router itself

                device_mac = dict(device_entry.connections).get(
                    dr.CONNECTION_NETWORK_MAC
                )
                if device_mac is None:
                    continue
                self.devices[device_mac] = {
                    "mac_address": device_mac,
                    "hostname": device_entry.name,
                    "active": False,
                    "last_seen": dt_util.utcnow() - timedelta(days=365),
                    "device_model": None,
                    "device_type": None,
                    "type": None,
                    "link_speed": None,
                    "signal_strength": None,
                    "ip_address": None,
                    "ssid": None,
                    "conn_ap_mac": None,
                    "blocked": None,
                }
        return True

    async def async_get_attached_devices(self) -> list[AttachedDevice]:
        """Get the devices connected to the router."""
        return await self.api.get_attached_devices()
        # if self.method_version == 1:
        #     async with self.api_lock:
        #         return await self.hass.async_add_executor_job(
        #             self.api.get_attached_devices
        #         )
        #
        # async with self.api_lock:
        #     return await self.hass.async_add_executor_job(
        #         self.api.get_attached_devices_2
        #     )

    async def async_update_device_trackers(self, now=None) -> bool:
        """Update Netgear devices."""
        new_device = False
        ntg_devices = await self.async_get_attached_devices()
        now = dt_util.utcnow()

        if ntg_devices is None:
            return new_device

        _LOGGER.debug("Netgear scan result: \n%s", ntg_devices)

        for ntg_device in ntg_devices:
            if ntg_device.mac_address is None:
                continue

            device_mac = dr.format_mac(ntg_device.mac_address)

            if not self.devices.get(device_mac):
                new_device = True

            # ntg_device is a namedtuple from the collections module that needs conversion to a dict through ._asdict method
            self.devices[device_mac] = asdict(ntg_device)
            self.devices[device_mac]["mac_address"] = device_mac
            self.devices[device_mac]["last_seen"] = now

        for device in self.devices.values():
            device["active"] = now - device["last_seen"] <= self._consider_home
            if not device["active"]:
                device["link_speed"] = None
                device["signal_strength"] = None
                device["ip_address"] = None
                device["ssid"] = None
                device["conn_ap_mac"] = None

        if new_device:
            _LOGGER.debug("Netgear tracker: new device found")

        return new_device

    async def async_get_traffic_meter(self) -> TrafficMeterStatistics:
        """Get the traffic meter data of the router."""
        return await self.api.get_traffic_meter_statistics()

    # async def async_get_speed_test(self) -> dict[str, Any] | None:
    #     """Perform a speed test and get the results from the router."""
    #     async with self.api_lock:
    #         return await self.hass.async_add_executor_job(
    #             self.api.get_new_speed_test_result
    #         )

    async def async_get_link_status(self) -> str:
        """Check the ethernet link status of the router."""
        return await self.api.get_ethernet_link_status()

    # async def async_allow_block_device(self, mac: str, allow_block: str) -> None:
    #     """Allow or block a device connected to the router."""
    #     async with self.api_lock:
    #         await self.hass.async_add_executor_job(
    #             self.api.allow_block_device, mac, allow_block
    #         )

    async def async_get_utilization(self) -> SystemInfo:
        """Get the system information about utilization of the router."""
        return await self.api.get_system_info()

    # async def async_reboot(self) -> None:
    #     """Reboot the router."""
    #     async with self.api_lock:
    #         await self.hass.async_add_executor_job(self.api.reboot)

    # async def async_check_new_firmware(self) -> dict[str, Any] | None:
    #     """Check for new firmware of the router."""
    #     async with self.api_lock:
    #         return await self.hass.async_add_executor_job(self.api.check_new_firmware)

    # async def async_update_new_firmware(self) -> None:
    #     """Update the router to the latest firmware."""
    #     async with self.api_lock:
    #         await self.hass.async_add_executor_job(self.api.update_new_firmware)

    # @property
    # def port(self) -> int:
    #     """Port used by the API."""
    #     return self.api.port
    #
    # @property
    # def ssl(self) -> bool:
    #     """SSL used by the API."""
    #     return self.api.ssl
