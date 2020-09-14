"""Support to interface with the Plex API."""
import logging

from homeassistant.components import media_source
import homeassistant.components.ais_dom.ais_global as ais_global
from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_APP,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_CHANNEL,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_EPISODE,
    MEDIA_CLASS_MOVIE,
    MEDIA_CLASS_MUSIC,
    MEDIA_CLASS_PLAYLIST,
    MEDIA_CLASS_PODCAST,
    MEDIA_CLASS_SEASON,
    MEDIA_CLASS_TRACK,
    MEDIA_CLASS_TV_SHOW,
    MEDIA_CLASS_VIDEO,
    MEDIA_TYPE_APP,
    MEDIA_TYPE_CHANNELS,
    MEDIA_TYPE_MUSIC,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source import const as media_source_const

from .const import DOMAIN


class UnknownMediaType(BrowseError):
    """Unknown media type."""


_LOGGER = logging.getLogger(__name__)


async def browse_media(hass, media_content_type=None, media_content_id=None):
    """Implement the websocket media browsing helper."""
    if media_content_type in [None, "library"]:
        return ais_media_library()

    if media_content_id.startswith(media_source_const.URI_SCHEME):
        result = await media_source.async_browse_media(hass, media_content_id)
        return result

    if media_content_id.startswith("ais_music"):
        return ais_music_library()

    if media_content_id.startswith("ais_favorites"):
        return ais_favorites_library(hass)

    response = None

    if response is None:
        raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")
    return response


def ais_media_library() -> BrowseMedia:
    """Create response payload to describe contents of a specific library."""
    ais_library_info = BrowseMedia(
        title="AIS Audio",
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id="library",
        media_content_type="library",
        can_play=False,
        can_expand=True,
        children=[],
    )

    ais_library_info.children.append(
        BrowseMedia(
            title="Dyski",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id=f"{media_source_const.URI_SCHEME}{media_source_const.DOMAIN}",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            thumbnail="http://www.ai-speaker.com/images/media-browser/harddisk.svg",
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Ulubione",
            media_class=MEDIA_CLASS_PLAYLIST,
            media_content_id="ais_favorites",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            thumbnail="http://www.ai-speaker.com/images/media-browser/heart.svg",
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Radio",
            media_class=MEDIA_CLASS_PODCAST,
            media_content_id="ais_radio",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            thumbnail="http://www.ai-speaker.com/images/media-browser/radio.svg",
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Podcast",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="ais_podcast",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            thumbnail="http://www.ai-speaker.com/images/media-browser/podcast.svg",
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Audio książki",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="ais_audio_books",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            thumbnail="http://www.ai-speaker.com/images/media-browser/book-music.svg",
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Muzyka",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="ais_music",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            thumbnail="http://www.ai-speaker.com/images/media-browser/music.svg",
        )
    )

    return ais_library_info


def ais_favorites_library(hass) -> BrowseMedia:
    d = hass.data["ais_bookmarks"]
    ais_favorites = []
    for fav in reversed(d.favorites):
        if "media_stream_image" in fav and fav["media_stream_image"] is not None:
            img = fav["media_stream_image"]
        else:
            img = "/static/icons/tile-win-310x150.png"
        if fav["name"].startswith(fav["source"]):
            name = fav["name"]
        else:
            name = (
                ais_global.G_NAME_FOR_AUDIO_NATURE.get(fav["source"], fav["source"])
                + " "
                + fav["name"]
            )

        ais_favorites.append(
            BrowseMedia(
                title=name,
                media_class=MEDIA_CLASS_MUSIC,
                media_content_id=fav["media_content_id"],
                media_content_type=MEDIA_TYPE_MUSIC,
                can_play=True,
                can_expand=False,
                thumbnail=img,
            )
        )

    root = BrowseMedia(
        title="Ulubione",
        media_class=MEDIA_CLASS_PLAYLIST,
        media_content_id="ais_favorites",
        media_content_type=MEDIA_TYPE_APP,
        can_expand=True,
        can_play=False,
        thumbnail="http://www.ai-speaker.com/images/media-browser/heart.svg",
        children=ais_favorites,
    )

    return root


def ais_music_library() -> BrowseMedia:
    """Create response payload to describe contents of a specific library."""
    ais_music_info = BrowseMedia(
        title="AIS Audio",
        media_class=MEDIA_CLASS_MUSIC,
        media_content_id="ais_music",
        media_content_type=MEDIA_TYPE_APP,
        can_play=False,
        can_expand=True,
        children=[],
    )

    ais_music_info.children.append(
        BrowseMedia(
            title="Spotify",
            media_class=MEDIA_CLASS_MUSIC,
            media_content_id="ais_music",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_music_info.children.append(
        BrowseMedia(
            title="YouTube",
            media_class=MEDIA_CLASS_VIDEO,
            media_content_id="ais_music",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    return ais_music_info
