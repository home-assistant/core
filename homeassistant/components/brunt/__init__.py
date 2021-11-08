"""The brunt component."""
from __future__ import annotations

import logging

from aiohttp.client_exceptions import ClientResponseError, ServerDisconnectedError
from brunt import BruntClientAsync

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Brunt using config flow."""
    hass.data.setdefault(DOMAIN, {})
    session = async_get_clientsession(hass)
    bapi = BruntClientAsync(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )
    try:
        await bapi.async_login()
    except ServerDisconnectedError as exc:
        raise ConfigEntryNotReady("Brunt not ready to connect.") from exc
    except ClientResponseError as exc:
        raise ConfigEntryAuthFailed(
            f"Brunt could not connect with username: {entry.data[CONF_USERNAME]}."
        ) from exc
    hass.data[DOMAIN][entry.entry_id] = bapi
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
