"""The emoncms component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER

PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data[CONF_URL]
    entry.async_on_unload(entry.add_update_listener(update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    LOGGER.debug(f"reloading config entry {entry.entry_id} {entry.data}")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
