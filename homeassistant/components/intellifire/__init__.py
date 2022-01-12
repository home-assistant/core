"""The IntelliFire integration."""
from __future__ import annotations

from intellifire4py import IntellifireAsync

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, LOGGER
from .coordinator import IntellifireDataUpdateCoordinator

PLATFORMS: list[str] = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IntelliFire from a config entry."""
    LOGGER.debug("Setting up config entry: %s", entry.unique_id)

    # Define the API Object
    api_object = IntellifireAsync(entry.data["host"])

    # Define the update coordinator
    coordinator = IntellifireDataUpdateCoordinator(
        hass=hass,
        api=api_object,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
