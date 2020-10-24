"""UK Environment Agency Flood Monitoring Integration."""

from .const import DOMAIN


async def async_setup(hass, config):
    """Set up devices."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass, entry):
    """Set up flood monitoring sensors for this config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload flood monitoring sensors."""
    return await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
