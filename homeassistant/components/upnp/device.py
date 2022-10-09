"""Home Assistant representation of an UPnP/IGD."""
from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse

from async_upnp_client.aiohttp import AiohttpSessionRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.profiles.igd import IgdDevice, StatusInfo
from getmac import get_mac_address

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    KIBIBYTES_PER_SEC_RECEIVED,
    KIBIBYTES_PER_SEC_SENT,
    LOGGER as _LOGGER,
    PACKETS_PER_SEC_RECEIVED,
    PACKETS_PER_SEC_SENT,
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

    factory = UpnpFactory(requester, non_strict=True)
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

    async def async_get_data(self) -> Mapping[str, Any]:
        """Get all data from device."""
        _LOGGER.debug("Getting data for device: %s", self)
        igd_state = await self._igd_device.async_get_traffic_and_status_data()

        return {
            TIMESTAMP: igd_state.timestamp,
            BYTES_RECEIVED: igd_state.bytes_received
            if igd_state.bytes_received is not None
            and not isinstance(igd_state.bytes_received, Exception)
            else None,
            BYTES_SENT: igd_state.bytes_sent
            if igd_state.bytes_received is not None
            and not isinstance(igd_state.bytes_received, Exception)
            else None,
            PACKETS_RECEIVED: igd_state.packets_received
            if igd_state.packets_received is not None
            and not isinstance(igd_state.packets_received, Exception)
            else None,
            PACKETS_SENT: igd_state.packets_sent
            if igd_state.packets_sent is not None
            and not isinstance(igd_state.packets_sent, Exception)
            else None,
            WAN_STATUS: igd_state.status_info.connection_status
            if isinstance(igd_state.status_info, StatusInfo)
            and igd_state.status_info.connection_status is not None
            and not isinstance(igd_state.status_info.connection_status, Exception)
            else None,
            ROUTER_UPTIME: igd_state.status_info.uptime
            if isinstance(igd_state.status_info, StatusInfo)
            and igd_state.status_info.uptime is not None
            and not isinstance(igd_state.status_info.uptime, Exception)
            else None,
            ROUTER_IP: igd_state.external_ip_address
            if igd_state.external_ip_address is not None
            and not isinstance(igd_state.external_ip_address, Exception)
            else None,
            KIBIBYTES_PER_SEC_RECEIVED: igd_state.kibibytes_per_sec_received,
            KIBIBYTES_PER_SEC_SENT: igd_state.kibibytes_per_sec_sent,
            PACKETS_PER_SEC_RECEIVED: igd_state.packets_per_sec_received,
            PACKETS_PER_SEC_SENT: igd_state.packets_per_sec_sent,
        }
