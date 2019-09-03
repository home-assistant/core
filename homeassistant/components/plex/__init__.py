"""Support to embed Plex."""
import logging
import plexapi.exceptions

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

from .const import (
    CONF_ENABLE_MEDIA_PLAYER,
    CONF_ENABLE_SENSOR,
    CONF_SERVER_IDENTIFIER,
    DOMAIN as PLEX_DOMAIN,
    PLEX_SERVER_CONFIG,
)
from .server import PlexServer

_LOGGER = logging.getLogger(__package__)


async def async_setup(hass, config):
    """Set up the Plex component."""
    return True


async def async_setup_entry(hass, entry):
    """Set up Plex from a config entry."""
    if PLEX_DOMAIN not in hass.data:
        hass.data[PLEX_DOMAIN] = {}

    platforms = []
    options = dict(entry.options)
    if options.get(CONF_ENABLE_MEDIA_PLAYER, True):
        platforms.append(MP_DOMAIN)
    if options.get(CONF_ENABLE_SENSOR, True):
        platforms.append(SENSOR_DOMAIN)

    if not platforms:
        return

    server_config = entry.data[PLEX_SERVER_CONFIG]
    server_id = entry.data[CONF_SERVER_IDENTIFIER]

    if server_id not in hass.data[PLEX_DOMAIN]:
        try:
            plex_server = await hass.async_add_executor_job(PlexServer, server_config)
        except (
            plexapi.exceptions.BadRequest,
            plexapi.exceptions.Unauthorized,
            plexapi.exceptions.NotFound,
        ) as error:
            _LOGGER.error(error)
            return
        else:
            hass.data[PLEX_DOMAIN][server_id] = plex_server

    for platform in platforms:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    return True
