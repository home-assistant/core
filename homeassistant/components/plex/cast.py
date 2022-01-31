"""Google Cast support for the Plex component."""
from __future__ import annotations

from pychromecast import Chromecast
from pychromecast.controllers.plex import PlexController

from homeassistant.components.cast.const import DOMAIN as CAST_DOMAIN
from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import MEDIA_CLASS_APP
from homeassistant.core import HomeAssistant

from . import async_browse_media as async_browse_plex_media, is_plex_media_id
from .const import PLEX_URI_SCHEME
from .services import lookup_plex_media


async def async_get_media_browser_root_object(cast_type: str) -> list[BrowseMedia]:
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
    media_id = media_id[len(PLEX_URI_SCHEME) :]
    media = lookup_plex_media(hass, media_type, media_id)
    if media is None:
        return
    controller = PlexController()
    chromecast.register_handler(controller)
    controller.play_media(media)


async def async_play_media(
    hass: HomeAssistant,
    cast_entity_id: str,
    chromecast: Chromecast,
    media_type: str,
    media_id: str,
) -> bool:
    """Play media."""
    if media_id and media_id.startswith(PLEX_URI_SCHEME):
        await hass.async_add_executor_job(
            _play_media, hass, chromecast, media_type, media_id
        )
        return True

    return False
