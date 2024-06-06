"""Initialize Leslie's Pool Water Tests integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import LesliesPoolApi
from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Leslie's Pool Water Tests from a config entry."""
    data = entry.data
    api = LesliesPoolApi(
        data["username"], data["password"], data["pool_profile_id"], data["pool_name"]
    )

    # Run the authenticate method in the executor to avoid blocking the event loop
    authenticated = await hass.async_add_executor_job(api.authenticate)
    if not authenticated:
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if DOMAIN in hass.data:
        hass.data[DOMAIN].pop(entry.entry_id)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
