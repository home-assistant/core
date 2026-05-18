"""The Lepro integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .api import LoproApiClient
from .const import CONF_API_HOST, DOMAIN
from .coordinator import LoproCoordinator

PLATFORMS = [Platform.LIGHT]

type LoproConfigEntry = ConfigEntry[LoproCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: LoproConfigEntry) -> bool:
    """Set up Lepro from a config entry."""
    # Restore api_host into hass.data so async_get_auth_implementation can use it
    # when refreshing tokens (called outside of the config flow context).
    hass.data.setdefault(DOMAIN, {})["api_host"] = entry.data[CONF_API_HOST]

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    client = LoproApiClient(hass, session, entry.data[CONF_API_HOST])
    coordinator = LoproCoordinator(hass, client, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LoproConfigEntry) -> bool:
    """Unload a Lepro config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
