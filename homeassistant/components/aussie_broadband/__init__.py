"""The Aussie Broadband integration."""
from __future__ import annotations

from aussiebb import AussieBB, AuthenticationException
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aussie Broadband from a config entry."""

    def create_client():
        try:
            return AussieBB(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
        except AuthenticationException as exc:
            raise ConfigEntryAuthFailed() from exc
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ) as exc:
            raise ConfigEntryNotReady() from exc

    hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = await hass.async_add_executor_job(create_client)
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
