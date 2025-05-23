"""The Microsoft Family Safety integration."""

from __future__ import annotations

from pyfamilysafety import Authenticator

from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import FamilySafetyConfigEntry, FamilySafetyCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: FamilySafetyConfigEntry
) -> bool:
    """Set up Microsoft Family Safety from a config entry."""
    auth = await Authenticator.create(
        entry.data[CONF_API_TOKEN], True, async_get_clientsession(hass)
    )
    entry.runtime_data = coordinator = FamilySafetyCoordinator(hass, entry, auth)
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: FamilySafetyConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
