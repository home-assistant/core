"""Support to embed Plex."""
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

from .const import CONF_ENABLE_MEDIA_PLAYER, CONF_ENABLE_SENSOR


async def async_setup(hass, config):
    """Set up the Plex component."""
    return True


async def async_setup_entry(hass, entry):
    """Set up Plex from a config entry."""
    platforms = []
    options = dict(entry.options)
    if options.get(CONF_ENABLE_MEDIA_PLAYER, True):
        platforms.append(MP_DOMAIN)
    if options.get(CONF_ENABLE_SENSOR, True):
        platforms.append(SENSOR_DOMAIN)

    for platform in platforms:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    return True
