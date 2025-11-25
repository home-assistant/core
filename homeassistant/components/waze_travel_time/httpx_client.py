"""Special httpx client for Waze Travel Time integration."""

import httpx

from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import create_async_httpx_client
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

DATA_HTTPX_ASYNC_CLIENT: HassKey[httpx.AsyncClient] = HassKey("httpx_async_client")


def create_transport() -> httpx.AsyncHTTPTransport:
    """Create a httpx transport which enforces the use of IPv4."""
    return httpx.AsyncHTTPTransport(local_address="0.0.0.0")


async def create_httpx_client(hass: HomeAssistant) -> httpx.AsyncClient:
    """Create a httpx client which enforces the use of IPv4."""
    if (client := hass.data[DOMAIN].get(DATA_HTTPX_ASYNC_CLIENT)) is None:
        transport = await hass.async_add_executor_job(create_transport)
        client = hass.data[DOMAIN][DATA_HTTPX_ASYNC_CLIENT] = create_async_httpx_client(
            hass, transport=transport
        )
    return client
