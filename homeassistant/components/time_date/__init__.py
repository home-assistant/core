"""The time_date component."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Time & Date from a config entry."""
    await remove_not_used_entities(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Time & Date config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def remove_not_used_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Cleanup entities not selected."""
    entity_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_reg, entry.entry_id)
    for entity in entities:
        splitter = entity.entity_id.split(".")
        check = splitter[1]
        if check not in entry.options["display_options"]:
            entity_reg.async_remove(entity.entity_id)
