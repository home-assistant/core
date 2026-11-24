"""Helpers for the Marstek integration."""

from aiomarstek import MarstekUDPClient

from homeassistant.components import network
from homeassistant.core import HomeAssistant


async def async_create_udp_client(hass: HomeAssistant) -> MarstekUDPClient:
    """Create a configured UDP client for this Home Assistant instance."""
    client = MarstekUDPClient()
    try:
        await client.async_setup()
        addresses = await network.async_get_ipv4_broadcast_addresses(hass)
        client.set_broadcast_addresses([str(address) for address in addresses])
    except BaseException:
        # Close the socket on any failure, including cancellation.
        await client.async_cleanup()
        raise

    return client
