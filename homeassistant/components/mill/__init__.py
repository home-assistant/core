"""The mill component."""

PLATFORMS = ["climate"]


async def async_setup_entry(hass, entry):
    """Set up the Mill heater."""
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
