"""The Coolmaster integration."""


async def async_setup(hass, config):
    """Set up Coolmaster components."""
    return True


async def async_setup_entry(hass, entry):
    """Set up Coolmaster from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "climate")
    )

    return True


async def async_unload_entry(hass, entry):
    """Unload a Coolmaster config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "climate")
