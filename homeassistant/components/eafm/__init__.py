"""UK Environment Agency Flood Monitoring Integration."""

from .const import DOMAIN

PLATFORMS = ["sensor"]


async def async_setup_entry(hass, entry):
    """Set up flood monitoring sensors for this config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    """Unload flood monitoring sensors."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
