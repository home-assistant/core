"""Home Assistant adapter for the Marstek client library."""

from __future__ import annotations

from aiomarstek import MarstekUDPClient

from homeassistant.components import network
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_udp_client(hass: HomeAssistant) -> MarstekUDPClient:
    """Return the shared UDP client configured for this Home Assistant instance."""
    store = hass.data.setdefault(DOMAIN, {})
    client = store.get("udp_client")
    if client is None:
        client = MarstekUDPClient()
        await client.async_setup()
        store["udp_client"] = client

    broadcast_addresses = await _async_get_broadcast_addresses(hass)
    if hasattr(client, "set_broadcast_addresses"):
        client.set_broadcast_addresses(broadcast_addresses)
    return client


async def _async_get_broadcast_addresses(hass: HomeAssistant) -> list[str]:
    """Return the enabled IPv4 broadcast addresses."""
    addresses = await network.async_get_ipv4_broadcast_addresses(hass)
    return [str(address) for address in addresses]
