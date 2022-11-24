"""Support for Google Mail."""
from __future__ import annotations

from aiohttp.client_exceptions import ClientError, ClientResponseError

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .const import DEFAULT_ACCESS, DOMAIN

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Mail from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed(
                "OAuth session is not valid, reauth required"
            ) from err
        raise ConfigEntryNotReady from err
    except ClientError as err:
        raise ConfigEntryNotReady from err

    if not async_entry_has_scopes(hass, entry):
        raise ConfigEntryAuthFailed("Required scopes are not present, reauth required")
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = session

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def async_entry_has_scopes(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Verify that the config entry desired scope is present in the oauth token."""
    return all(
        feature in entry.data[CONF_TOKEN]["scope"].split(" ")
        for feature in DEFAULT_ACCESS
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        for service_name in hass.services.async_services()[DOMAIN]:
            hass.services.async_remove(DOMAIN, service_name)

    return unload_ok
