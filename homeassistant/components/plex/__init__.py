"""Support to embed Plex."""
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN


async def async_setup(hass, config):
    """Set up the Plex component."""
    return True


async def async_setup_entry(hass, entry):
    """Set up Plex from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, MP_DOMAIN)
    )
    return True
