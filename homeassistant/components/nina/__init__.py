"""The Nina integration."""

from __future__ import annotations

from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    ALL_MATCH_REGEX,
    CONF_AREA_FILTER,
    CONF_FILTER_CORONA,
    CONF_FILTERS,
    CONF_HEADLINE_FILTER,
    NO_MATCH_REGEX,
)
from .coordinator import NinaConfigEntry, NINADataUpdateCoordinator

PLATFORMS: list[str] = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NinaConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    migrate_config(hass, entry)

    coordinator = NINADataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NinaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def migrate_config(hass: HomeAssistant, entry: NinaConfigEntry):
    """Migrate the config to the new format."""
    if CONF_FILTERS in entry.data:
        return

    new_data: dict[str, Any] = {**entry.data, CONF_FILTERS: {}}

    if CONF_HEADLINE_FILTER not in entry.data:
        filter_regex = NO_MATCH_REGEX

        if entry.data.get(CONF_FILTER_CORONA, None):
            filter_regex = ".*corona.*"

        new_data[CONF_FILTERS][CONF_HEADLINE_FILTER] = filter_regex
        new_data.pop(CONF_FILTER_CORONA, None)
    else:
        new_data[CONF_FILTERS][CONF_HEADLINE_FILTER] = entry.data[CONF_HEADLINE_FILTER]
        new_data.pop(CONF_HEADLINE_FILTER, None)

    if CONF_AREA_FILTER not in entry.data:
        new_data[CONF_FILTERS][CONF_AREA_FILTER] = ALL_MATCH_REGEX
    else:
        new_data[CONF_FILTERS][CONF_AREA_FILTER] = entry.data[CONF_AREA_FILTER]
        new_data.pop(CONF_AREA_FILTER, None)

    hass.config_entries.async_update_entry(entry, data=new_data)
