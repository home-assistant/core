"""The Samsung TV integration."""


async def async_setup(hass, config):
    """Set up the Samsung TV integration."""
    return True


async def async_setup_entry(hass, entry):
    """Set up the Samsung TV platform."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "media_player")
    )

    return True
