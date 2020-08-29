"""The media_source integration."""
import re

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.media_player.const import ATTR_MEDIA_CONTENT_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.loader import bind_hass

from .const import DOMAIN, URI_SCHEME, URI_SCHEME_REGEX
from .models import Media

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the media_source component."""
    hass.data[DOMAIN] = {}
    hass.components.websocket_api.async_register_command(websocket_browse_media)
    await async_process_integration_platforms(
        hass, DOMAIN, _process_media_source_platform
    )
    return True


async def _process_media_source_platform(hass, domain, platform):
    """Process a media source platform."""
    platform, cb = await platform.async_setup_media_source(hass)
    hass.data[DOMAIN][platform] = cb


@bind_hass
async def async_find_media(hass: HomeAssistant, location=None):
    """Iterate platform integrations to build media list."""
    if not location or location == URI_SCHEME:
        media = Media(None, "Media Sources", URI_SCHEME)
        media.is_dir = True
        media.children = [
            Media(platform, platform, f"{URI_SCHEME}{platform}", is_dir=True)
            for platform in hass.data[DOMAIN].keys()
        ]
        return media

    matches = re.match(URI_SCHEME_REGEX, location)
    if not matches:
        return None

    platform = matches.group("platform")
    path = matches.group("path")

    if not platform:
        return None

    return await hass.data[DOMAIN][platform](hass, path)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "media_source/browse_media",
        vol.Optional(
            ATTR_MEDIA_CONTENT_ID,
            "media_ids",
            "media_content_type and media_content_id must be provided together",
        ): str,
    }
)
@websocket_api.async_response
async def websocket_browse_media(hass, connection, msg):
    """
    Browse available media.

    To use, media_player integrations can implement MediaPlayerEntity.async_browse_media()
    """
    media_content_id = msg.get(ATTR_MEDIA_CONTENT_ID)

    return await async_find_media(hass, media_content_id)
