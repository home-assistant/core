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

    if not entry.data.get(CONF_KEY) or not entry.data.get(CONF_SECRET):
        raise ConfigEntryNotReady("Missing API credentials")

    # Create the planner in executor since constructor makes blocking HTTP calls
    try:
        planner = await hass.async_add_executor_job(
            vasttrafik.JournyPlanner, entry.data[CONF_KEY], entry.data[CONF_SECRET]
        )
    except Exception as err:
        _LOGGER.error("Failed to initialize Västtrafik API: %s", err)
        raise ConfigEntryNotReady(
            f"Unable to initialize Västtrafik API: {err}"
        ) from err

    # Store the planner instance in runtime_data
    entry.runtime_data = planner

    # Set up update listener to reload when subentries change
    entry.add_update_listener(async_reload_entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: VasttrafikConfigEntry) -> None:
    """Reload config entry when subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: VasttrafikConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
