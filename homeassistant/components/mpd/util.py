"""Utility functions for the MPD integration."""

from zeroconf.asyncio import AsyncServiceInfo

from homeassistant.components import zeroconf
from homeassistant.core import HomeAssistant

from .const import LOGGER


async def async_resolve_host(hass: HomeAssistant, host: str) -> str:
    """Resolve hostname using zeroconf if it's a .local domain."""
    if not host.endswith(".local"):
        return host

    try:
        aiozc = await zeroconf.async_get_async_instance(hass)
        # Try to resolve the hostname using zeroconf's address lookup
        addresses = await aiozc.async_get_host_by_name(host)
        if addresses:
            resolved = addresses[0]
            LOGGER.debug("Resolved %s to %s via zeroconf", host, resolved)
            return resolved
    except Exception as ex:  # noqa: BLE001
        LOGGER.debug("Failed to resolve %s via zeroconf: %s", host, ex)

    # Fallback to standard asyncio DNS resolution
    import asyncio
    try:
        infos = await asyncio.get_event_loop().getaddrinfo(host, None)
        for family, _, _, _, sockaddr in infos:
            if family in (2, 10):  # socket.AF_INET, socket.AF_INET6
                resolved = sockaddr[0]
                LOGGER.debug("Resolved %s to %s via getaddrinfo", host, resolved)
                return resolved
    except Exception as ex:  # noqa: BLE001
        LOGGER.debug("Failed to resolve %s via getaddrinfo: %s", host, ex)
    return host
