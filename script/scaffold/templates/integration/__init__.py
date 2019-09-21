"""The NEW_NAME integration."""

from .const import DOMAIN


async def async_setup(hass, config):
    """Set up the NEW_NAME integration."""
    hass.data[DOMAIN] = config.get(DOMAIN, {})
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry for NEW_NAME."""
    # TODO forward the entry for each platform that you want to set up.
    # hass.async_create_task(
    #     hass.config_entries.async_forward_entry_setup(entry, "media_player")
    # )

    return True
