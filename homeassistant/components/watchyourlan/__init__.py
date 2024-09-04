"""Support for WatchYourLAN."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WatchYourLAN from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Load the update interval from options if available
    update_interval = entry.options.get("update_interval", 5)

    # Store the config entry data in hass.data for use by platforms
    hass.data[DOMAIN][entry.entry_id] = {
        "host": entry.data[CONF_HOST],
        "port": entry.data[CONF_PORT],
        "ssl": entry.data[CONF_SSL],
        "url": entry.data["url"],
        "update_interval": update_interval,  # Use the user-configured interval or default
    }

    await hass.config_entries.async_forward_entry_setup(entry, Platform.SENSOR)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and remove the entities."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(
        entry, Platform.SENSOR
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
