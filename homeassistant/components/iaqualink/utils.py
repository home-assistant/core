"""Utility functions for Aqualink devices."""

from collections.abc import Awaitable

import httpx
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError


def error_detail(err: Exception) -> str:
    """Return a non-empty error detail for iaqualink exceptions."""
    if detail := str(err):
        return detail
    return type(err).__name__


async def await_or_reraise(
    hass: HomeAssistant,
    config_entry: ConfigEntry | None,
    awaitable: Awaitable,
) -> None:
    """Execute API call while catching service exceptions."""
    try:
        await awaitable
    except AqualinkServiceUnauthorizedException as auth_exception:
        if config_entry is not None:
            config_entry.async_start_reauth(hass)
        raise ConfigEntryAuthFailed(
            "Invalid credentials for iAquaLink"
        ) from auth_exception
    except TimeoutError as timeout_exception:
        raise HomeAssistantError(
            f"Aqualink error: {error_detail(timeout_exception)}"
        ) from timeout_exception
    except (AqualinkServiceException, httpx.HTTPError) as svc_exception:
        raise HomeAssistantError(
            f"Aqualink error: {error_detail(svc_exception)}"
        ) from svc_exception
