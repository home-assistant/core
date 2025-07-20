"""The AirPatrol integration."""

from __future__ import annotations

import logging

from airpatrol.api import AirPatrolAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import AirPatrolDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


class AirPatrolConfigEntry(ConfigEntry["AirPatrolDataUpdateCoordinator"]):
    """AirPatrol config entry."""


async def async_setup_entry(hass: HomeAssistant, entry: AirPatrolConfigEntry) -> bool:
    """Set up AirPatrol from a config entry."""
    # Create API instance
    session = async_get_clientsession(hass)

    try:
        # Check if we have a stored access token
        if "access_token" in entry.data:
            # Use stored access token for authentication
            token = entry.data["access_token"]
            uid = entry.unique_id  # Set the UID from the config entry
            api = AirPatrolAPI(session, token, uid)
            # Validate the token is still valid by making a test API call
            await api.get_data()
            _LOGGER.debug("Using stored access token for authentication")
        else:
            # Fall back to email/password authentication
            _LOGGER.debug("No access token found, using email/password authentication")
            api = await AirPatrolAPI.authenticate(
                session, entry.data["email"], entry.data["password"]
            )
            # Store the new access token using the proper method
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, "access_token": api.get_access_token()}
            )
    except Exception as err:
        _LOGGER.error("Failed to connect to AirPatrol: %s", err)
        raise ConfigEntryAuthFailed(f"Failed to connect to AirPatrol: {err}") from err

    # Create coordinator and store it in runtime_data
    coordinator = AirPatrolDataUpdateCoordinator(hass, api, entry)
    entry.runtime_data = coordinator

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirPatrolConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: AirPatrolConfigEntry) -> None:
    """Reload the config entry and clear the pairings cache."""
    # Clear the pairings cache to force a fresh fetch
    if entry.runtime_data and hasattr(entry.runtime_data, "api"):
        entry.runtime_data.api.clear_pairings_cache()
        _LOGGER.debug("Cleared pairings cache for reload")

    # Reload the config entry
    await hass.config_entries.async_reload(entry.entry_id)
