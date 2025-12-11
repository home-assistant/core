"""Constants for the MPD integration."""

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
        # Query for the A/AAAA records
        info = AsyncServiceInfo(
            "_mpd._tcp.local.",
            f"{host.removesuffix('.local')}._mpd._tcp.local.",
        )
        await info.async_request(aiozc.zeroconf, 3000)

        if info.parsed_addresses():
            resolved = info.parsed_addresses()[0]
            LOGGER.debug("Resolved %s to %s via zeroconf", host, resolved)
            return resolved
    except Exception as ex:  # noqa: BLE001
        LOGGER.debug("Failed to resolve %s via zeroconf: %s", host, ex)

    return host
