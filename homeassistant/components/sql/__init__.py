"""The sql component."""
from __future__ import annotations

from homeassistant.components.recorder import CONF_DB_URL, get_instance
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for options."""
    await hass.config_entries.async_reload(entry.entry_id)


def remove_configured_db_url_if_not_needed(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove db url from config if it matches recorder database."""
    new_options = {**entry.options, **{CONF_DB_URL: None}}
    hass.config_entries.async_update_entry(
        entry,
        options=new_options,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SQL from a config entry."""
    if entry.options[CONF_DB_URL] == get_instance(hass).db_url:
        remove_configured_db_url_if_not_needed(hass, entry)

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload SQL config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
