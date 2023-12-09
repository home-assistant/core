"""The A. O. Smith integration."""
from __future__ import annotations

from dataclasses import dataclass

from py_aosmith import AOSmithAPIClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .coordinator import AOSmithCoordinator

PLATFORMS: list[Platform] = [Platform.WATER_HEATER]


@dataclass
class AOSmithData:
    """Data for the A. O. Smith integration."""

    coordinator: AOSmithCoordinator
    client: AOSmithAPIClient


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up A. O. Smith from a config entry."""
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    session = aiohttp_client.async_get_clientsession(hass)
    client = AOSmithAPIClient(email, password, session)
    coordinator = AOSmithCoordinator(hass, client)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = AOSmithData(
        coordinator=coordinator, client=client
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
