"""The Diyanet integration."""

from __future__ import annotations

from pydiyanet import DiyanetApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import CONF_LOCATION_ID, DOMAIN
from .coordinator import DiyanetCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type DiyanetConfigEntry = ConfigEntry[DiyanetCoordinator]

# This integration is configured via UI only
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: DiyanetConfigEntry) -> bool:
    """Set up Diyanet from a config entry."""

    # Get credentials from config entry
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    location_id = entry.data[CONF_LOCATION_ID]

    # Create API client
    session = async_get_clientsession(hass)
    client = DiyanetApiClient(session, email, password)

    # Create coordinator
    coordinator = DiyanetCoordinator(hass, client, location_id, entry)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Set up daily scheduled updates at 00:05
    await coordinator.async_setup()

    # Store coordinator in runtime_data
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DiyanetConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Unload the coordinator's scheduled task
        entry.runtime_data.shutdown()
    return unload_ok
