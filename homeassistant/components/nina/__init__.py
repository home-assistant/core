"""The Nina integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    ALL_MATCH_REGEX,
    CONF_AREA_FILTER,
    CONF_FILTER_CORONA,
    CONF_HEADLINE_FILTER,
    DOMAIN,
    NO_MATCH_REGEX,
)
from .coordinator import NINADataUpdateCoordinator

PLATFORMS: list[str] = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    if CONF_HEADLINE_FILTER not in entry.data:
        filter_regex = NO_MATCH_REGEX

        if entry.data[CONF_FILTER_CORONA]:
            filter_regex = ".*corona.*"

        new_data = {**entry.data, CONF_HEADLINE_FILTER: filter_regex}
        new_data.pop(CONF_FILTER_CORONA, None)
        hass.config_entries.async_update_entry(entry, data=new_data)

    if CONF_AREA_FILTER not in entry.data:
        new_data = {**entry.data, CONF_AREA_FILTER: ALL_MATCH_REGEX}
        hass.config_entries.async_update_entry(entry, data=new_data)

    coordinator = NINADataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
