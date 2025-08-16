"""The Västtrafik integration."""

from __future__ import annotations

import logging

import vasttrafik

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryNotReady,
    ConfigEntryState,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_KEY, CONF_SECRET, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type VasttrafikConfigEntry = ConfigEntry[vasttrafik.JournyPlanner]


async def async_setup_entry(hass: HomeAssistant, entry: VasttrafikConfigEntry) -> bool:
    """Set up Västtrafik from a config entry."""

    if entry.data.get("is_departure_board"):
        # This is a departure board entry - get credentials from main integration
        main_entry = _get_main_entry(hass)
        if not main_entry:
            raise ConfigEntryNotReady("Main Västtrafik integration not found")

        # Check if main entry is loaded and has runtime_data
        if main_entry.state != ConfigEntryState.LOADED or not hasattr(main_entry, 'runtime_data') or not main_entry.runtime_data:
            raise ConfigEntryNotReady("Main Västtrafik integration not ready")

        entry.runtime_data = main_entry.runtime_data
    else:
        # This is the main integration - set up API client
        if not entry.data.get(CONF_KEY) or not entry.data.get(CONF_SECRET):
            raise ConfigEntryNotReady("Missing API credentials")

        # Create the planner in executor since constructor makes blocking HTTP calls
        try:
            planner = await hass.async_add_executor_job(
                vasttrafik.JournyPlanner,
                entry.data[CONF_KEY],
                entry.data[CONF_SECRET]
            )
        except Exception as err:
            _LOGGER.error("Failed to initialize Västtrafik API: %s", err)
            raise ConfigEntryNotReady(f"Unable to initialize Västtrafik API: {err}") from err

        # Store the planner instance in runtime_data
        entry.runtime_data = planner

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _get_main_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Get the main Västtrafik integration entry."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("is_departure_board") is not True:
            return entry
    return None




async def async_unload_entry(hass: HomeAssistant, entry: VasttrafikConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
