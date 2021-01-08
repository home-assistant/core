"""The mill component."""


async def async_setup(hass, config):
    """Set up the Mill platform."""
    return True


async def async_setup_entry(hass, entry):
    """Set up the Mill heater."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "climate")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(
        config_entry, "climate"
    )
    return unload_ok
