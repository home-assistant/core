"""Utility helpers for the WiiM integration."""

from __future__ import annotations

from urllib.parse import urlparse

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import NoURLAvailableError, get_url


class InvalidHomeAssistantURLError(HomeAssistantError):
    """Error to indicate Home Assistant does not expose a usable URL."""


def get_homeassistant_local_host(hass: HomeAssistant) -> str:
    """Return the Home Assistant hostname that WiiM devices should use."""
    try:
        base_url = get_url(hass, prefer_external=False)
    except NoURLAvailableError as err:
        raise InvalidHomeAssistantURLError(
            "Failed to determine Home Assistant URL"
        ) from err

    if local_host := urlparse(base_url).hostname:
        return local_host

    raise InvalidHomeAssistantURLError("Failed to determine Home Assistant URL")
