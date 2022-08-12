"""Google Cast support for the Plex component."""
from __future__ import annotations

from pychromecast import Chromecast
from pychromecast.controllers.plex import PlexController

from homeassistant.components.cast.const import DOMAIN as CAST_DOMAIN
from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import MEDIA_CLASS_APP
from homeassistant.core import HomeAssistant

from . import async_browse_media as async_browse_plex_media, is_plex_media_id
from .services import process_plex_payload


async def async_get_media_browser_root_object(
    hass: HomeAssistant, cast_type: str
) -> list[BrowseMedia]:
    """Create a root object for media browsing."""
    return [
        BrowseMedia(
            title="Plex",
            media_class=MEDIA_CLASS_APP,
            media_content_id="",
            media_content_type="plex",
            thumbnail="https://brands.home-assistant.io/_/plex/logo.png",
            can_play=False,
            can_expand=True,
        )
    ]


async def async_browse_media(
    hass: HomeAssistant,
    media_content_type: str,
    media_content_id: str,
    cast_type: str,
) -> BrowseMedia | None:
    """Browse media."""
    if is_plex_media_id(media_content_id):
        return await async_browse_plex_media(
            hass, media_content_type, media_content_id, platform=CAST_DOMAIN
        )
    if media_content_type == "plex":
        return await async_browse_plex_media(hass, None, None, platform=CAST_DOMAIN)
    return None


def _play_media(
    hass: HomeAssistant, chromecast: Chromecast, media_type: str, media_id: str
) -> None:
    """Play media."""
    result = process_plex_payload(hass, media_type, media_id)
    controller = PlexController()
    chromecast.register_handler(controller)
    offset_in_s = result.offset / 1000
    controller.play_media(result.media, offset=offset_in_s)


async def async_play_media(
    hass: HomeAssistant,
    cast_entity_id: str,
    chromecast: Chromecast,
    media_type: str,
    media_id: str,
) -> bool:
    """Play media."""
    if is_plex_media_id(media_id):
        await hass.async_add_executor_job(
            _play_media, hass, chromecast, media_type, media_id
        )
        return True

    return False
