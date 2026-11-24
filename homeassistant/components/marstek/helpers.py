"""Helpers for the Marstek integration."""

import asyncio

from aiomarstek import MarstekUDPClient

from homeassistant.components import network
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .coordinator import MARSTEK_UDP_CLIENT

MARSTEK_UDP_CLIENT_LOCK: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_udp_client_lock")


async def async_get_udp_client(hass: HomeAssistant) -> MarstekUDPClient:
    """Return the shared UDP client, creating it on first use."""
    # Every client binds the same UDP port, so config flows and entries
    # must share one client to avoid receiving each other's replies.
    async with hass.data.setdefault(MARSTEK_UDP_CLIENT_LOCK, asyncio.Lock()):
        if (udp_client := hass.data.get(MARSTEK_UDP_CLIENT)) is not None:
            return udp_client
        udp_client = await async_create_udp_client(hass)
        hass.data[MARSTEK_UDP_CLIENT] = udp_client

    async def close_udp_client(_: Event) -> None:
        """Clean up the shared UDP client when Home Assistant stops."""
        await udp_client.async_cleanup()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_udp_client)
    return udp_client


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
