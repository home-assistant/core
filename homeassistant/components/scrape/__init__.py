"""The scrape component."""
from __future__ import annotations

import httpx

from homeassistant.components.rest.data import RestData
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HEADERS,
    CONF_PASSWORD,
    CONF_RESOURCE,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Scrape from a config entry."""

    resource: str = entry.options[CONF_RESOURCE]
    method: str = "GET"
    payload: str | None = None
    headers: str | None = entry.options.get(CONF_HEADERS)
    verify_ssl: bool = entry.options[CONF_VERIFY_SSL]
    username: str | None = entry.options.get(CONF_USERNAME)
    password: str | None = entry.options.get(CONF_PASSWORD)

    auth: httpx.DigestAuth | tuple[str, str] | None = None
    if username and password:
        if entry.options.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
            auth = httpx.DigestAuth(username, password)
        else:
            auth = (username, password)

    rest = RestData(hass, method, resource, auth, headers, None, payload, verify_ssl)
    await rest.async_update()

    if rest.data is None:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = rest

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Scrape config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
