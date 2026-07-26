"""Utility helpers for the WiiM integration."""

from urllib.parse import urlparse

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
