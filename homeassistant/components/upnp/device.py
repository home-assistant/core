"""Home Assistant representation of an UPnP/IGD."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from ipaddress import IPv4Address
from typing import Any
from urllib.parse import urlparse

from async_upnp_client import UpnpFactory
from async_upnp_client.aiohttp import AiohttpSessionRequester
from async_upnp_client.device_updater import DeviceUpdater
from async_upnp_client.profiles.igd import IgdDevice

from homeassistant.components import ssdp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from .const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    CONF_LOCAL_IP,
    DISCOVERY_HOSTNAME,
    DISCOVERY_LOCATION,
    DISCOVERY_NAME,
    DISCOVERY_ST,
    DISCOVERY_UDN,
    DISCOVERY_UNIQUE_ID,
    DISCOVERY_USN,
    DOMAIN,
    DOMAIN_CONFIG,
    LOGGER as _LOGGER,
    PACKETS_RECEIVED,
    PACKETS_SENT,
    TIMESTAMP,
)


def discovery_info_to_discovery(discovery_info: Mapping) -> Mapping:
    """Convert a SSDP-discovery to 'our' discovery."""
    location = discovery_info[ssdp.ATTR_SSDP_LOCATION]
    parsed = urlparse(location)
    hostname = parsed.hostname
    return {
        DISCOVERY_UDN: discovery_info[ssdp.ATTR_UPNP_UDN],
        DISCOVERY_ST: discovery_info[ssdp.ATTR_SSDP_ST],
        DISCOVERY_LOCATION: discovery_info[ssdp.ATTR_SSDP_LOCATION],
        DISCOVERY_USN: discovery_info[ssdp.ATTR_SSDP_USN],
        DISCOVERY_HOSTNAME: hostname,
    }


def _get_local_ip(hass: HomeAssistant) -> IPv4Address | None:
    """Get the configured local ip."""
    if DOMAIN in hass.data and DOMAIN_CONFIG in hass.data[DOMAIN]:
        local_ip = hass.data[DOMAIN][DOMAIN_CONFIG].get(CONF_LOCAL_IP)
        if local_ip:
            return IPv4Address(local_ip)
    return None


class Device:
    """Home Assistant representation of a UPnP/IGD device."""

    def __init__(self, igd_device: IgdDevice, device_updater: DeviceUpdater) -> None:
        """Initialize UPnP/IGD device."""
        self._igd_device = igd_device
        self._device_updater = device_updater
        self.coordinator: DataUpdateCoordinator = None

    @classmethod
    async def async_discover(cls, hass: HomeAssistant) -> list[Mapping]:
        """Discover UPnP/IGD devices."""
        _LOGGER.debug("Discovering UPnP/IGD devices")
        discoveries = []
        for ssdp_st in IgdDevice.DEVICE_TYPES:
            for discovery_info in ssdp.async_get_discovery_info_by_st(hass, ssdp_st):
                discoveries.append(discovery_info_to_discovery(discovery_info))
        return discoveries

    @classmethod
    async def async_supplement_discovery(
        cls, hass: HomeAssistant, discovery: Mapping
    ) -> Mapping:
        """Get additional data from device and supplement discovery."""
        location = discovery[DISCOVERY_LOCATION]
        device = await Device.async_create_device(hass, location)
        discovery[DISCOVERY_NAME] = device.name
        discovery[DISCOVERY_HOSTNAME] = device.hostname
        discovery[DISCOVERY_UNIQUE_ID] = discovery[DISCOVERY_USN]

        return discovery

    @classmethod
    async def async_create_device(
        cls, hass: HomeAssistant, ssdp_location: str
    ) -> Device:
        """Create UPnP/IGD device."""
        # Build async_upnp_client requester.
        session = async_get_clientsession(hass)
        requester = AiohttpSessionRequester(session, True, 10)

        # Create async_upnp_client device.
        factory = UpnpFactory(requester, disable_state_variable_validation=True)
        upnp_device = await factory.async_create_device(ssdp_location)

        # Create profile wrapper.
        igd_device = IgdDevice(upnp_device, None)

        # Create updater.
        local_ip = _get_local_ip(hass)
        device_updater = DeviceUpdater(
            device=upnp_device, factory=factory, source_ip=local_ip
        )

        return cls(igd_device, device_updater)

    async def async_start(self) -> None:
        """Start the device updater."""
        await self._device_updater.async_start()

    async def async_stop(self) -> None:
        """Stop the device updater."""
        await self._device_updater.async_stop()

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
    def hostname(self) -> str:
        """Get the hostname."""
        url = self._igd_device.device.device_url
        parsed = urlparse(url)
        return parsed.hostname

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
            TIMESTAMP: dt_util.utcnow(),
            BYTES_RECEIVED: values[0],
            BYTES_SENT: values[1],
            PACKETS_RECEIVED: values[2],
            PACKETS_SENT: values[3],
        }
