"""Set up Tonewinner from a config entry."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Tonewinner from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Pass a LIST of platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["media_player"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "media_player")

    # Unregister the service if it exists
    service_key = f"{entry.entry_id}_service"
    if service_key in hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, "send_raw")
        del hass.data[DOMAIN][service_key]

    hass.data[DOMAIN].pop(entry.entry_id)
    return True
