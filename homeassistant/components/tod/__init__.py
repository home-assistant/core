"""The Times of the Day integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_AFTER, CONF_BEFORE, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_AFTER_TIME, CONF_BEFORE_TIME, CONF_TIME, DOMAIN

__all__ = [
    "DOMAIN",
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up Times of the Day from a config entry."""
    await hass.config_entries.async_forward_entry_setups(
        entry, (Platform.BINARY_SENSOR,)
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(
        entry, (Platform.BINARY_SENSOR,)
    )


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate fixed time transitions to the time choices."""
    if entry.version == 1:
        options = dict(entry.options)
        options[CONF_AFTER] = {CONF_TIME: options.pop(CONF_AFTER_TIME)}
        options[CONF_BEFORE] = {CONF_TIME: options.pop(CONF_BEFORE_TIME)}
        hass.config_entries.async_update_entry(entry, options=options, version=2)
