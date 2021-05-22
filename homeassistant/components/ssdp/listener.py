"""The SSDP integration."""
from __future__ import annotations

import asyncio
from ipaddress import IPv4Address, IPv6Address
import logging

from async_upnp_client.ssdp import (
    SSDP_IP_V4,
    SSDP_IP_V6,
    SSDP_MX,
    SSDP_ST_ALL,
    SSDP_TARGET_V4,
    SSDP_TARGET_V6,
    SsdpProtocol,
    build_ssdp_search_packet,
    get_ssdp_socket,
)

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)


class SSDPListener:
    """Class to listen for SSDP."""

    def __init__(self, async_callback, source_ip):
        """Init the ssdp listener class."""
        self._async_callback = async_callback
        self._source_ip = source_ip
        self._targets = None
        self._transport = None
        self._is_ipv4 = None

    @callback
    def async_search(self) -> None:
        """Start an SSDP search."""
        self._transport.sendto(
            build_ssdp_search_packet(self._target_data, SSDP_MX, SSDP_ST_ALL),
            self._target,
        )

    async def _async_on_data(self, request_line, headers) -> None:
        _LOGGER.debug("New data: %s %s", request_line, headers)
        await self._async_callback(headers)

    async def _async_on_connect(self, transport):
        self._transport = transport
        self.async_search()

    async def async_start(self):
        """Start the listener."""
        self._is_ipv4 = self._source_ip.version == 4
        self._target_data = SSDP_TARGET_V4 if self._is_ipv4 else SSDP_TARGET_V6
        target_ip = (
            IPv4Address(SSDP_IP_V4) if self._is_ipv4 else IPv6Address(SSDP_IP_V6)
        )
        sock, source, self._target = get_ssdp_socket(self._source_ip, target_ip)
        sock.bind(source)
        loop = asyncio.get_running_loop()
        await loop.create_datagram_endpoint(
            lambda: SsdpProtocol(
                loop, on_connect=self._async_on_connect, on_data=self._async_on_data
            ),
            sock=sock,
        )

    @callback
    def async_stop(self):
        """Stop the listener."""
        self._transport.close()
