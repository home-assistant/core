"""Home Assistant adapter for the Marstek client library."""

from aiomarstek import MarstekUDPClient

from homeassistant.components import network
from homeassistant.core import HomeAssistant


async def async_create_udp_client(hass: HomeAssistant) -> MarstekUDPClient:
    """Create a configured UDP client for this Home Assistant instance."""
    client = MarstekUDPClient()
    await client.async_setup()
    broadcast_addresses = await _async_get_broadcast_addresses(hass)
    client.set_broadcast_addresses(broadcast_addresses)
    return client


async def _async_get_broadcast_addresses(hass: HomeAssistant) -> list[str]:
    """Return the enabled IPv4 broadcast addresses."""
    addresses = await network.async_get_ipv4_broadcast_addresses(hass)
    return [str(address) for address in addresses]
