"""Support for AdGuard Home."""

from __future__ import annotations

from typing import TYPE_CHECKING

from adguardhome import AdGuardHome
import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_FORCE,
    DOMAIN,
    SERVICE_ADD_URL,
    SERVICE_DISABLE_URL,
    SERVICE_ENABLE_URL,
    SERVICE_REFRESH,
    SERVICE_REMOVE_URL,
)

if TYPE_CHECKING:
    from . import AdGuardConfigEntry

SERVICE_URL_SCHEMA = vol.Schema({vol.Required(CONF_URL): vol.Any(cv.url, cv.path)})
SERVICE_ADD_URL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_URL): vol.Any(cv.url, cv.path),
    }
)
SERVICE_REFRESH_SCHEMA = vol.Schema(
    {vol.Optional(CONF_FORCE, default=False): cv.boolean}
)


def _get_adguard_instance(hass: HomeAssistant) -> AdGuardHome:
    """Get the AdGuardHome instance."""
    entries: list[AdGuardConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    if len(entries) == 1:
        return entries[0].runtime_data.client
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="single_loaded_instance_only"
    )


async def add_url(call: ServiceCall) -> None:
    """Service call to add a new filter subscription to AdGuard Home."""
    await _get_adguard_instance(call.hass).filtering.add_url(
        allowlist=False, name=call.data[CONF_NAME], url=call.data[CONF_URL]
    )


async def remove_url(call: ServiceCall) -> None:
    """Service call to remove a filter subscription from AdGuard Home."""
    await _get_adguard_instance(call.hass).filtering.remove_url(
        allowlist=False, url=call.data[CONF_URL]
    )


async def enable_url(call: ServiceCall) -> None:
    """Service call to enable a filter subscription in AdGuard Home."""
    await _get_adguard_instance(call.hass).filtering.enable_url(
        allowlist=False, url=call.data[CONF_URL]
    )


async def disable_url(call: ServiceCall) -> None:
    """Service call to disable a filter subscription in AdGuard Home."""
    await _get_adguard_instance(call.hass).filtering.disable_url(
        allowlist=False, url=call.data[CONF_URL]
    )


async def refresh(call: ServiceCall) -> None:
    """Service call to refresh the filter subscriptions in AdGuard Home."""
    await _get_adguard_instance(call.hass).filtering.refresh(
        allowlist=False, force=call.data[CONF_FORCE]
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the AdGuard services."""

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_URL, add_url, schema=SERVICE_ADD_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_URL, remove_url, schema=SERVICE_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ENABLE_URL, enable_url, schema=SERVICE_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DISABLE_URL, disable_url, schema=SERVICE_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, refresh, schema=SERVICE_REFRESH_SCHEMA
    )
