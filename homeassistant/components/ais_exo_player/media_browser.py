"""Support to interface with the Plex API."""
import logging

from homeassistant.components import media_source
from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_APP,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_CHANNEL,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_EPISODE,
    MEDIA_CLASS_MOVIE,
    MEDIA_CLASS_PLAYLIST,
    MEDIA_CLASS_SEASON,
    MEDIA_CLASS_TRACK,
    MEDIA_CLASS_TV_SHOW,
    MEDIA_CLASS_VIDEO,
    MEDIA_TYPE_APP,
    MEDIA_TYPE_CHANNELS,
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
            thumbnail="https://cdn2.iconfinder.com/data/icons/folders-22/512/Folder_Mac_Music.png",
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Ulubione",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="ais_radio",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            thumbnail="https://1.bp.blogspot.com/-qZTfIjt9AXk/TxMWUFLKWLI/AAAAAAAAAWk/bwQqSX-Z3H0/s1600/Graphic__Music__Headphones__Heart_xlarge.gif",
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Radio",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="ais_radio",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            thumbnail="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a6/Radio.svg/1024px-Radio.svg.png",
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
            thumbnail="https://www.mclellanmarketing.com/wp-content/uploads/2016/04/podcasting_opt.jpg",
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
            thumbnail="https://lh3.googleusercontent.com/proxy/wp_i9gaVHpM75OVae5HyUoBcgMyW-ssPsSS1tCK7QerVBjeKIE8-ruKLCVmjjc7_AwFvDhWDLYKWnurpPOQoSlA",
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
            thumbnail="https://mybroadband.co.za/news/wp-content/uploads/2019/03/YouTube-Music-vs-Spotify.png",
        )
    )

    return ais_library_info


def ais_music_library() -> BrowseMedia:
    """Create response payload to describe contents of a specific library."""
    ais_music_info = BrowseMedia(
        title="AIS Audio",
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id="ais_music",
        media_content_type=MEDIA_TYPE_APP,
        can_play=False,
        can_expand=True,
        children=[],
        thumbnail="https://mybroadband.co.za/news/wp-content/uploads/2019/03/YouTube-Music-vs-Spotify.png",
    )

    ais_music_info.children.append(
        BrowseMedia(
            title="Spotify",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="ais_music",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            thumbnail="https://www.theyucatantimes.com/wp-content/uploads/2020/08/spotify-logo.png",
        )
    )
    ais_music_info.children.append(
        BrowseMedia(
            title="YouTube",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="ais_music",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            thumbnail="https://www.internetmatters.org/wp-content/uploads/2020/01/youtube.png",
        )
    )
    return ais_music_info
