"""The Diyanet integration."""

from __future__ import annotations

from pydiyanet import DiyanetApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LOCATION_ID
from .coordinator import DiyanetCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type DiyanetConfigEntry = ConfigEntry[DiyanetCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DiyanetConfigEntry) -> bool:
    """Set up Diyanet from a config entry."""

    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    location_id = entry.data[CONF_LOCATION_ID]

    session = async_get_clientsession(hass)
    client = DiyanetApiClient(session, email, password)

    coordinator = DiyanetCoordinator(hass, client, location_id, entry)

    await coordinator.async_config_entry_first_refresh()

    # Set up daily scheduled updates at 00:05
    await coordinator.async_setup()

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
