"""Home Assistant representation of an UPnP/IGD."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from functools import partial
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse

from async_upnp_client.aiohttp import AiohttpSessionRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import UpnpError
from async_upnp_client.profiles.igd import IgdDevice, StatusInfo
from getmac import get_mac_address

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import utcnow

from .const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    LOGGER as _LOGGER,
    PACKETS_RECEIVED,
    PACKETS_SENT,
    ROUTER_IP,
    ROUTER_UPTIME,
    TIMESTAMP,
    WAN_STATUS,
)


async def async_get_mac_address_from_host(hass: HomeAssistant, host: str) -> str | None:
    """Get mac address from host."""
    ip_addr = ip_address(host)
    if ip_addr.version == 4:
        mac_address = await hass.async_add_executor_job(
            partial(get_mac_address, ip=host)
        )
    else:
        mac_address = await hass.async_add_executor_job(
            partial(get_mac_address, ip6=host)
        )
    return mac_address


async def async_create_device(hass: HomeAssistant, ssdp_location: str) -> Device:
    """Create UPnP/IGD device."""
    session = async_get_clientsession(hass, verify_ssl=False)
    requester = AiohttpSessionRequester(session, with_sleep=True, timeout=20)

    factory = UpnpFactory(requester, disable_state_variable_validation=True)
    upnp_device = await factory.async_create_device(ssdp_location)

    # Create profile wrapper.
    igd_device = IgdDevice(upnp_device, None)
    device = Device(hass, igd_device)

    return device


class Device:
    """Home Assistant representation of a UPnP/IGD device."""

    def __init__(self, hass: HomeAssistant, igd_device: IgdDevice) -> None:
        """Initialize UPnP/IGD device."""
        self.hass = hass
        self._igd_device = igd_device
        self.coordinator: DataUpdateCoordinator | None = None
        self.original_udn: str | None = None

    async def async_get_mac_address(self) -> str | None:
        """Get mac address."""
        if not self.host:
            return None

        return await async_get_mac_address_from_host(self.hass, self.host)

    @property
    def udn(self) -> str:
        """Get the UDN."""
        return self._igd_device.udn

    @property
    def name(self) -> str:
        """Get the name."""
        return self._igd_device.name

    @property
    def manufacturer(self) -> str:
        """Get the manufacturer."""
        return self._igd_device.manufacturer

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._igd_device.model_name

    @property
    def device_type(self) -> str:
        """Get the device type."""
        return self._igd_device.device_type

    @property
    def usn(self) -> str:
        """Get the USN."""
        return f"{self.udn}::{self.device_type}"

    @property
    def unique_id(self) -> str:
        """Get the unique id."""
        return self.usn

    @property
    def host(self) -> str | None:
        """Get the hostname."""
        url = self._igd_device.device.device_url
        parsed = urlparse(url)
        return parsed.hostname

    @property
    def device_url(self) -> str:
        """Get the device_url of the device."""
        return self._igd_device.device.device_url

    @property
    def serial_number(self) -> str | None:
        """Get the serial number."""
        return self._igd_device.device.serial_number

    def __str__(self) -> str:
        """Get string representation."""
        return f"IGD Device: {self.name}/{self.udn}::{self.device_type}"

    async def async_get_traffic_data(self) -> Mapping[str, Any]:
        """
        Get all traffic data in one go.

        Traffic data consists of:
        - total bytes sent
        - total bytes received
        - total packets sent
        - total packats received

        Data is timestamped.
        """
        _LOGGER.debug("Getting traffic statistics from device: %s", self)

        values = await asyncio.gather(
            self._igd_device.async_get_total_bytes_received(),
            self._igd_device.async_get_total_bytes_sent(),
            self._igd_device.async_get_total_packets_received(),
            self._igd_device.async_get_total_packets_sent(),
        )

        return {
            TIMESTAMP: utcnow(),
            BYTES_RECEIVED: values[0],
            BYTES_SENT: values[1],
            PACKETS_RECEIVED: values[2],
            PACKETS_SENT: values[3],
        }

    async def async_get_status(self) -> Mapping[str, Any]:
        """Get connection status, uptime, and external IP."""
        _LOGGER.debug("Getting status for device: %s", self)

        values = await asyncio.gather(
            self._igd_device.async_get_status_info(),
            self._igd_device.async_get_external_ip_address(),
            return_exceptions=True,
        )
        status_info: StatusInfo | None = None
        router_ip: str | None = None

        for idx, value in enumerate(values):
            if isinstance(value, UpnpError):
                # Not all routers support some of these items although based
                # on defined standard they should.
                _LOGGER.debug(
                    "Exception occurred while trying to get status %s for device %s: %s",
                    "status" if idx == 1 else "external IP address",
                    self,
                    str(value),
                )
                continue

            if isinstance(value, Exception):
                raise value

            if isinstance(value, StatusInfo):
                status_info = value
            elif isinstance(value, str):
                router_ip = value

        return {
            WAN_STATUS: status_info[0] if status_info is not None else None,
            ROUTER_UPTIME: status_info[2] if status_info is not None else None,
            ROUTER_IP: router_ip,
        }
