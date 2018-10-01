"""Hass representation of an UPnP/IGD."""
import asyncio
from ipaddress import IPv4Address

import aiohttp

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import get_local_ip

from .const import LOGGER as _LOGGER


class Device:
    """Hass representation of an UPnP/IGD."""

    def __init__(self, igd_device):
        """Initializer."""
        self._igd_device = igd_device
        self._mapped_ports = []

    @classmethod
    async def async_create_device(cls,
                                  hass: HomeAssistantType,
                                  ssdp_description: str):
        """Create UPnP/IGD device."""
        # build async_upnp_client requester
        from async_upnp_client.aiohttp import AiohttpSessionRequester
        session = async_get_clientsession(hass)
        requester = AiohttpSessionRequester(session, True)

        # create async_upnp_client device
        from async_upnp_client import UpnpFactory
        factory = UpnpFactory(requester,
                              disable_state_variable_validation=True)
        upnp_device = await factory.async_create_device(ssdp_description)

        # wrap with async_upnp_client IgdDevice
        from async_upnp_client.igd import IgdDevice
        igd_device = IgdDevice(upnp_device, None)

        return cls(igd_device)

    @property
    def udn(self):
        """Get the UDN."""
        return self._igd_device.udn

    @property
    def name(self):
        """Get the name."""
        return self._igd_device.name

    async def async_add_port_mappings(self, ports, local_ip=None):
        """Add port mappings."""
        # determine local ip, ensure sane IP
        if local_ip is None:
            local_ip = get_local_ip()

        if local_ip == '127.0.0.1':
            _LOGGER.error(
                'Could not create port mapping, our IP is 127.0.0.1')
        local_ip = IPv4Address(local_ip)

        # create port mappings
        for external_port, internal_port in ports.items():
            await self._async_add_port_mapping(external_port,
                                               local_ip,
                                               internal_port)
            self._mapped_ports.append(external_port)

    async def _async_add_port_mapping(self,
                                      external_port,
                                      local_ip,
                                      internal_port):
        """Add a port mapping."""
        # create port mapping
        from async_upnp_client import UpnpError
        _LOGGER.info('Creating port mapping %s:%s:%s (TCP)',
                     external_port, local_ip, internal_port)
        try:
            await self._igd_device.async_add_port_mapping(
                remote_host=None,
                external_port=external_port,
                protocol='TCP',
                internal_port=internal_port,
                internal_client=local_ip,
                enabled=True,
                description="Home Assistant",
                lease_duration=None)

            self._mapped_ports.append(external_port)
        except (asyncio.TimeoutError, aiohttp.ClientError, UpnpError):
            _LOGGER.error('Could not add port mapping: %s:%s:%s',
                          external_port, local_ip, internal_port)

    async def async_delete_port_mappings(self):
        """Remove a port mapping."""
        for port in self._mapped_ports:
            await self._async_delete_port_mapping(port)

    async def _async_delete_port_mapping(self, external_port):
        """Remove a port mapping."""
        from async_upnp_client import UpnpError
        _LOGGER.info('Deleting port mapping %s (TCP)', external_port)
        try:
            await self._igd_device.async_delete_port_mapping(
                remote_host=None,
                external_port=external_port,
                protocol='TCP')

            self._mapped_ports.remove(external_port)
        except (asyncio.TimeoutError, aiohttp.ClientError, UpnpError):
            _LOGGER.error('Could not delete port mapping')

    async def async_get_total_bytes_received(self):
        """Get total bytes received."""
        return await self._igd_device.async_get_total_bytes_received()

    async def async_get_total_bytes_sent(self):
        """Get total bytes sent."""
        return await self._igd_device.async_get_total_bytes_sent()

    async def async_get_total_packets_received(self):
        """Get total packets received."""
        # pylint: disable=invalid-name
        return await self._igd_device.async_get_total_packets_received()

    async def async_get_total_packets_sent(self):
        """Get total packets sent."""
        return await self._igd_device.async_get_total_packets_sent()
