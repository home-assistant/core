"""The Nina integration."""

from __future__ import annotations

from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    _LOGGER,
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
    coordinator = NINADataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NinaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: NinaConfigEntry) -> bool:
    """Migrate the config to the new format."""

    version = entry.version
    minor_version = entry.minor_version

    _LOGGER.debug("Migrating from version %s.%s", version, minor_version)
    if entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    new_data: dict[str, Any] = {**entry.data, CONF_FILTERS: {}}

    if version == 1 and minor_version == 1:
        if CONF_HEADLINE_FILTER not in entry.data:
            filter_regex = NO_MATCH_REGEX

            if entry.data.get(CONF_FILTER_CORONA, None):
                filter_regex = ".*corona.*"

            new_data[CONF_HEADLINE_FILTER] = filter_regex
            new_data.pop(CONF_FILTER_CORONA, None)

        if CONF_AREA_FILTER not in entry.data:
            new_data[CONF_AREA_FILTER] = ALL_MATCH_REGEX

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            minor_version=2,
        )
        minor_version = 2

    if version == 1 and minor_version == 2:
        new_data[CONF_FILTERS][CONF_HEADLINE_FILTER] = entry.data[CONF_HEADLINE_FILTER]
        new_data.pop(CONF_HEADLINE_FILTER, None)

        new_data[CONF_FILTERS][CONF_AREA_FILTER] = entry.data[CONF_AREA_FILTER]
        new_data.pop(CONF_AREA_FILTER, None)

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            minor_version=3,
        )

    return True
