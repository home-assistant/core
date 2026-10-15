"""Utilities for the LinkPlay component."""

from aiohttp import ClientSession
from linkplay.utils import async_create_unverified_client_session

from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import Event, HomeAssistant, callback

from .const import SESSION_KEY


async def async_get_client_session(hass: HomeAssistant) -> ClientSession:
    """Get a ClientSession that can be used with LinkPlay devices."""
    if SESSION_KEY not in hass.data:
        clientsession: ClientSession = await async_create_unverified_client_session()

        @callback
        def _async_close_websession(event: Event) -> None:
            """Close websession."""
            clientsession.detach()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_websession)
        hass.data[SESSION_KEY] = clientsession
        return clientsession

    return hass.data[SESSION_KEY]
