"""Utilities for the LinkPlay component."""

from aiohttp import ClientSession
from linkplay.utils import async_create_unverified_client_session

from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import Event, HomeAssistant, callback

from .const import DATA_SESSION, DOMAIN


async def async_get_client_session(hass: HomeAssistant) -> ClientSession:
    """Get a ClientSession that can be used with LinkPlay devices."""
    hass.data.setdefault(DOMAIN, {})
    if DATA_SESSION not in hass.data[DOMAIN]:
        clientsession: ClientSession = await async_create_unverified_client_session()

        @callback
        def _async_close_websession(event: Event) -> None:
            """Close websession."""
            clientsession.detach()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_websession)
        hass.data[DOMAIN][DATA_SESSION] = clientsession
        return clientsession

    session: ClientSession = hass.data[DOMAIN][DATA_SESSION]
    return session
