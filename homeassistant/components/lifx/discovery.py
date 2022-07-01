"""Home Assistant specific discovery of LIFX devices."""
from __future__ import annotations

import asyncio
from ipaddress import IPv4Address, IPv6Address
import logging

from aiolifx.aiolifx import LifxDiscovery, Light

from homeassistant.components import network
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class LifxNetworkScanner:
    """Scan all network interfaces for any active bulb."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the scanner."""
        self.hass = hass

    async def found_lifx_devices(self) -> bool:
        """Return True if a lifx device was found on an enabled interface."""

        enabled_ips: list[
            IPv4Address | IPv6Address
        ] = await network.async_get_enabled_source_ips(self.hass)
        source_ips: list[IPv4Address] = [
            ip_address
            for ip_address in enabled_ips
            if ip_address.version == 4 and ip_address.is_loopback is False
        ]

        tasks: list[asyncio.Task] = []
        discoveries: list[LifxDiscovery] = []
        for source_ip in source_ips:
            _LOGGER.debug("Looking for LIFX devices using %s", str(source_ip))
            scan_manager = ScanManager(source_ip)
            source_ip_discovery = LifxDiscovery(self.hass.loop, scan_manager)
            discoveries.append(source_ip_discovery)
            source_ip_discovery.start(listen_ip=str(source_ip))
            tasks.append(self.hass.loop.create_task(scan_manager.source_ip()))

        (done, pending) = await asyncio.wait(tasks, timeout=1)

        for discovery in discoveries:
            discovery.cleanup()

        for task in pending:
            task.cancel()

        lifx_ip_addresses: list[IPv4Address] = [task.result() for task in done]
        return len(lifx_ip_addresses) > 0


class ScanManager:
    """Temporary manager for LIFX network discovery."""

    def __init__(self, source_ip: IPv4Address) -> None:
        """Initialize the manager."""
        self._event = asyncio.Event()
        self._source_ip = source_ip

    async def source_ip(self) -> IPv4Address:
        """Return the source IP address if any device is discovered."""
        await self._event.wait()
        return self._source_ip

    def register(self, bulb: Light) -> None:
        """Handle detected bulb."""
        self._event.set()

    def unregister(self, bulb: Light) -> None:
        """Handle disappearing bulb."""
