"""Zeroconf helper functions for Shelly integration."""

from __future__ import annotations

import logging

from zeroconf import IPVersion
from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

_LOGGER = logging.getLogger(__name__)


async def async_lookup_device_by_name(
    aiozc: AsyncZeroconf, device_name: str
) -> tuple[str, int] | None:
    """Look up a Shelly device by name via zeroconf.

    Args:
        aiozc: AsyncZeroconf instance
        device_name: Device name (e.g., "ShellyPlugUS-C049EF8873E8")

    Returns:
        Tuple of (host, port) if found, None otherwise

    """
    service_name = f"{device_name}._http._tcp.local."

    _LOGGER.debug("Active lookup for: %s", service_name)
    service_info = AsyncServiceInfo("_http._tcp.local.", service_name)

    if await service_info.async_request(aiozc.zeroconf, 5000):
        addresses = service_info.parsed_addresses(IPVersion.V4Only)
        if addresses and service_info.port:
            host = addresses[0]
            port = service_info.port
            _LOGGER.debug("Found device via active lookup at %s:%s", host, port)
            return (host, port)
        _LOGGER.debug("Active lookup found service but no IPv4 addresses or port")
    else:
        _LOGGER.debug("Active lookup did not find service")

    return None
