"""The google_travel_time component."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get,
)

from .const import DOMAIN

DATA_LISTENER = "listener"
PLATFORMS = ["sensor"]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the Google Maps Travel Time component."""
    hass.data[DOMAIN] = {DATA_LISTENER: {}}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Maps Travel Time from a config entry."""
    hass.data[DOMAIN][DATA_LISTENER][entry.entry_id] = []
    if entry.unique_id is not None:
        hass.config_entries.async_update_entry(entry, unique_id=None)

        ent_reg = async_get(hass)
        for entity in async_entries_for_config_entry(ent_reg, entry.entry_id):
            ent_reg.async_update_entity(entity.entity_id, new_unique_id=entry.entry_id)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    hass.data[DOMAIN][DATA_LISTENER][entry.entry_id].append(
        entry.add_update_listener(async_reload_entry)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        for remove_listener in hass.data[DOMAIN][DATA_LISTENER].pop(entry.entry_id):
            remove_listener()

    return unload_ok


async def async_reload_entry(hass, entry):
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)
