"""Home Assistant representation of an UPnP/IGD."""

from __future__ import annotations

from datetime import datetime
from functools import partial
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse

from async_upnp_client.aiohttp import AiohttpSessionRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.profiles.igd import IgdDevice
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


def get_preferred_location(locations: set[str]) -> str:
    """Get the preferred location (an IPv4 location) from a set of locations."""
    # Prefer IPv4 over IPv6.
    for location in locations:
        if location.startswith(("http://[", "https://[")):
            continue

        return location

    # Fallback to any.
    for location in locations:
        return location

    raise ValueError("No location found")


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


async def async_create_device(hass: HomeAssistant, location: str) -> Device:
    """Create UPnP/IGD device."""
    session = async_get_clientsession(hass, verify_ssl=False)
    requester = AiohttpSessionRequester(session, with_sleep=True, timeout=20)

    factory = UpnpFactory(requester, non_strict=True)
    upnp_device = await factory.async_create_device(location)

    # Create profile wrapper.
    igd_device = IgdDevice(upnp_device, None)
    return Device(hass, igd_device)


class Device:
    """Home Assistant representation of a UPnP/IGD device."""

    def __init__(self, hass: HomeAssistant, igd_device: IgdDevice) -> None:
        """Initialize UPnP/IGD device."""
        self.hass = hass
        self._igd_device = igd_device
        self.coordinator: (
            DataUpdateCoordinator[dict[str, str | datetime | int | float | None]] | None
        ) = None
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
        parsed = urlparse(self.device_url)
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

    async def async_get_data(self) -> dict[str, str | datetime | int | float | None]:
        """Get all data from device."""
        _LOGGER.debug("Getting data for device: %s", self)
        igd_state = await self._igd_device.async_get_traffic_and_status_data()
        status_info = igd_state.status_info
        if status_info is not None and not isinstance(status_info, BaseException):
            wan_status = status_info.connection_status
            router_uptime = status_info.uptime
        else:
            wan_status = None
            router_uptime = None

        def get_value(value: Any) -> Any:
            if value is None or isinstance(value, BaseException):
                return None

            return value

        return {
            TIMESTAMP: igd_state.timestamp,
            BYTES_RECEIVED: get_value(igd_state.bytes_received),
            BYTES_SENT: get_value(igd_state.bytes_sent),
            PACKETS_RECEIVED: get_value(igd_state.packets_received),
            PACKETS_SENT: get_value(igd_state.packets_sent),
            WAN_STATUS: wan_status,
            ROUTER_UPTIME: router_uptime,
            ROUTER_IP: get_value(igd_state.external_ip_address),
            KIBIBYTES_PER_SEC_RECEIVED: igd_state.kibibytes_per_sec_received,
            KIBIBYTES_PER_SEC_SENT: igd_state.kibibytes_per_sec_sent,
            PACKETS_PER_SEC_RECEIVED: igd_state.packets_per_sec_received,
            PACKETS_PER_SEC_SENT: igd_state.packets_per_sec_sent,
        }
