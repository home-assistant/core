"""Utility helpers for the WiiM integration."""

from urllib.parse import urlparse

from async_upnp_client.utils import async_get_local_ip

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import DOMAIN


class InvalidHomeAssistantURLError(HomeAssistantError):
    """Error to indicate Home Assistant does not expose a usable URL."""


def get_homeassistant_local_host(hass: HomeAssistant) -> str:
    """Return the Home Assistant hostname that WiiM devices should use."""
    try:
        base_url = get_url(hass, prefer_external=False)
    except NoURLAvailableError as err:
        raise InvalidHomeAssistantURLError(
            translation_domain=DOMAIN,
            translation_key="missing_homeassistant_url",
        ) from err

    if local_host := urlparse(base_url).hostname:
        return local_host

    raise InvalidHomeAssistantURLError(
        translation_domain=DOMAIN,
        translation_key="missing_homeassistant_url",
    )


async def async_get_event_callback_host(hass: HomeAssistant, upnp_location: str) -> str:
    """Return the address a WiiM device should send UPnP events to."""
    if hass.config.internal_url:
        return get_homeassistant_local_host(hass)

    try:
        _, local_ip = await async_get_local_ip(upnp_location, hass.loop)
    except OSError:
        return get_homeassistant_local_host(hass)

    return local_ip
