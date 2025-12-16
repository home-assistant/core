"""The Västtrafik integration."""

from __future__ import annotations

import logging

import vasttrafik

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_KEY, CONF_SECRET

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type VasttrafikConfigEntry = ConfigEntry[vasttrafik.JournyPlanner]


async def async_setup_entry(hass: HomeAssistant, entry: VasttrafikConfigEntry) -> bool:
    """Set up Västtrafik from a config entry."""

    try:
        planner = await hass.async_add_executor_job(
            vasttrafik.JournyPlanner, entry.data[CONF_KEY], entry.data[CONF_SECRET]
        )
    except vasttrafik.Error as err:
        raise ConfigEntryNotReady(
            f"Unable to initialize Västtrafik API: {err}"
        ) from err

    entry.runtime_data = planner

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: VasttrafikConfigEntry) -> None:
    """Reload entry when subentries change."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: VasttrafikConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
