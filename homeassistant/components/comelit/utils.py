"""Utils for Comelit."""

from aiohttp import ClientSession, CookieJar

from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client


async def async_client_session(hass: HomeAssistant) -> ClientSession:
    """Return a new aiohttp session."""
    return aiohttp_client.async_create_clientsession(
        hass, verify_ssl=False, cookie_jar=CookieJar(unsafe=True)
    )
