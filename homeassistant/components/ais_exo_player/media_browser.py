"""Support to interface with the Plex API."""
import logging

import async_timeout

from homeassistant.components import ais_audiobooks_service, ais_cloud, media_source
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
from homeassistant.helpers import aiohttp_client

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

    if media_content_id.startswith("ais_bookmarks"):
        return ais_bookmarks_library(hass)

    if media_content_id.startswith("ais_radio"):
        return ais_radio_library(hass, media_content_id)

    if media_content_id.startswith("ais_podcast"):
        return await ais_podcast_library(hass, media_content_id)

    if media_content_id.startswith("ais_audio_books"):
        return await ais_audio_books_library(hass, media_content_id)

    response = None

    if response is None:
        raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")
    return response


def ais_media_library() -> BrowseMedia:
    """Create response payload to describe contents of a specific library."""
    ais_library_info = BrowseMedia(
        title="AIS Audio",
        media_class=MEDIA_CLASS_APP,
        media_content_id="library",
        media_content_type="library",
        can_play=False,
        can_expand=True,
        children=[],
    )

    ais_library_info.children.append(
        BrowseMedia(
            title="Dyski",
            media_class="nas",
            media_content_id=f"{media_source_const.URI_SCHEME}{media_source_const.DOMAIN}",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Ulubione",
            media_class="heart",
            media_content_id="ais_favorites",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Zakładki",
            media_class="bookmark",
            media_content_id="ais_bookmarks",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Radio",
            media_class="radio",
            media_content_id="ais_radio",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Podcast",
            media_class=MEDIA_CLASS_PODCAST,
            media_content_id="ais_podcast",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Audio książki",
            media_class="book",
            media_content_id="ais_audio_books",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Muzyka",
            media_class=MEDIA_CLASS_MUSIC,
            media_content_id="ais_music",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )

    return ais_library_info


async def ais_audio_books_library(hass, media_content_id) -> BrowseMedia:
    ais_cloud_ws = ais_cloud.AisCloudWS(hass)
    data = ais_audiobooks_service.AudioBooksData(hass, None)
    import json
    import os

    if media_content_id == "ais_audio_books":
        # get authors
        path = hass.config.path() + ais_audiobooks_service.PERSISTENCE_AUDIOBOOKS
        if not os.path.isfile(path):
            return
        with open(path) as file:
            all_books = json.loads(file.read())

        authors = []
        for item in all_books:
            if item["author"] not in authors:
                authors.append(item["author"])

        ais_authors = []
        for author in authors:
            ais_authors.append(
                BrowseMedia(
                    title=author,
                    media_class="book",
                    media_content_id="ais_audio_books/" + author,
                    media_content_type=MEDIA_TYPE_APP,
                    can_play=False,
                    can_expand=True,
                )
            )

        root = BrowseMedia(
            title="Autorzy",
            media_class=MEDIA_CLASS_ARTIST,
            media_content_id="ais_audio_books",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            children=ais_authors,
        )
        return root
    elif media_content_id.count("/") == 1:
        # get podcasts for types
        ws_resp = ais_cloud_ws.audio_name(
            ais_global.G_AN_PODCAST, media_content_id.replace("ais_podcast/", "")
        )
        json_ws_resp = ws_resp.json()
        ais_radio_stations = []
        for item in json_ws_resp["data"]:
            ais_radio_stations.append(
                BrowseMedia(
                    title=item["NAME"],
                    media_class=MEDIA_CLASS_PODCAST,
                    media_content_id=media_content_id + "/" + item["LOOKUP_URL"],
                    media_content_type=MEDIA_TYPE_CHANNELS,
                    can_play=False,
                    can_expand=True,
                    thumbnail=item["IMAGE_URL"],
                )
            )
        root = BrowseMedia(
            title="Podcast",
            media_class=MEDIA_CLASS_PODCAST,
            media_content_id=media_content_id,
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            children=ais_radio_stations,
        )
        return root
    else:
        # get podcast tracks
        try:
            lookup_url = media_content_id.split("/", 2)[2]
            web_session = aiohttp_client.async_get_clientsession(hass)
            import feedparser

            #  3 sec should be enough
            with async_timeout.timeout(30):
                ws_resp = await web_session.get(lookup_url)
                response_text = await ws_resp.text()
                d = feedparser.parse(response_text)
                ais_podcast_episodes = []
                for e in d.entries:
                    try:
                        thumbnail = d.feed.image.href
                    except Exception:
                        thumbnail = ""
                    ais_podcast_episodes.append(
                        BrowseMedia(
                            title=e.title,
                            media_class=MEDIA_CLASS_EPISODE,
                            media_content_id=e.enclosures[0]["url"],
                            media_content_type=MEDIA_TYPE_MUSIC,
                            can_play=True,
                            can_expand=False,
                            thumbnail=thumbnail,
                        )
                    )
                root = BrowseMedia(
                    title="Podcast",
                    media_class=MEDIA_CLASS_PODCAST,
                    media_content_id=media_content_id,
                    media_content_type=MEDIA_TYPE_CHANNELS,
                    can_expand=True,
                    can_play=False,
                    children=ais_podcast_episodes,
                )
                return root
        except Exception as e:
            _LOGGER.warning("Timeout when reading RSS %s", lookup_url)


async def ais_podcast_library(hass, media_content_id) -> BrowseMedia:
    ais_cloud_ws = ais_cloud.AisCloudWS(hass)
    if media_content_id == "ais_podcast":
        # get podcast types
        ws_resp = ais_cloud_ws.audio_type(ais_global.G_AN_PODCAST)
        json_ws_resp = ws_resp.json()
        ais_podcast_types = []
        for item in json_ws_resp["data"]:
            ais_podcast_types.append(
                BrowseMedia(
                    title=item,
                    media_class=MEDIA_CLASS_PODCAST,
                    media_content_id="ais_podcast/" + item,
                    media_content_type=MEDIA_TYPE_APP,
                    can_play=False,
                    can_expand=True,
                )
            )
        root = BrowseMedia(
            title="Podcasty",
            media_class=MEDIA_CLASS_PODCAST,
            media_content_id="ais_podcast",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            children=ais_podcast_types,
        )
        return root
    elif media_content_id.count("/") == 1:
        # get podcasts for types
        ws_resp = ais_cloud_ws.audio_name(
            ais_global.G_AN_PODCAST, media_content_id.replace("ais_podcast/", "")
        )
        json_ws_resp = ws_resp.json()
        ais_radio_stations = []
        for item in json_ws_resp["data"]:
            ais_radio_stations.append(
                BrowseMedia(
                    title=item["NAME"],
                    media_class=MEDIA_CLASS_PODCAST,
                    media_content_id=media_content_id + "/" + item["LOOKUP_URL"],
                    media_content_type=MEDIA_TYPE_CHANNELS,
                    can_play=False,
                    can_expand=True,
                    thumbnail=item["IMAGE_URL"],
                )
            )
        root = BrowseMedia(
            title="Podcast",
            media_class=MEDIA_CLASS_PLAYLIST,
            media_content_id=media_content_id,
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            children=ais_radio_stations,
        )
        return root
    else:
        # get podcast tracks
        try:
            lookup_url = media_content_id.split("/", 2)[2]
            web_session = aiohttp_client.async_get_clientsession(hass)
            import feedparser

            #  3 sec should be enough
            with async_timeout.timeout(30):
                ws_resp = await web_session.get(lookup_url)
                response_text = await ws_resp.text()
                d = feedparser.parse(response_text)
                ais_podcast_episodes = []
                for e in d.entries:
                    try:
                        thumbnail = d.feed.image.href
                    except Exception:
                        thumbnail = ""
                    ais_podcast_episodes.append(
                        BrowseMedia(
                            title=e.title,
                            media_class=MEDIA_CLASS_PLAYLIST,
                            media_content_id=e.enclosures[0]["url"],
                            media_content_type=MEDIA_TYPE_MUSIC,
                            can_play=True,
                            can_expand=False,
                            thumbnail=thumbnail,
                        )
                    )
                root = BrowseMedia(
                    title="Podcast",
                    media_class=MEDIA_CLASS_PODCAST,
                    media_content_id=media_content_id,
                    media_content_type=MEDIA_TYPE_CHANNELS,
                    can_expand=True,
                    can_play=False,
                    thumbnail="http://www.ai-speaker.com/images/media-browser/podcast.svg",
                    children=ais_podcast_episodes,
                )
                return root
        except Exception as e:
            _LOGGER.warning("Timeout when reading RSS %s", lookup_url)


def ais_radio_library(hass, media_content_id) -> BrowseMedia:
    ais_cloud_ws = ais_cloud.AisCloudWS(hass)
    if media_content_id == "ais_radio":
        # get
        ws_resp = ais_cloud_ws.audio_type(ais_global.G_AN_RADIO)
        json_ws_resp = ws_resp.json()
        # ais_radio_types = [ais_global.G_FAVORITE_OPTION]
        ais_radio_types = []
        for item in json_ws_resp["data"]:
            ais_radio_types.append(
                BrowseMedia(
                    title=item,
                    media_class=MEDIA_CLASS_DIRECTORY,
                    media_content_id="ais_radio/" + item,
                    media_content_type=MEDIA_TYPE_APP,
                    can_play=False,
                    can_expand=True,
                )
            )
        root = BrowseMedia(
            title="Radio",
            media_class=MEDIA_CLASS_PLAYLIST,
            media_content_id="ais_radio",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            thumbnail="http://www.ai-speaker.com/images/media-browser/radio.svg",
            children=ais_radio_types,
        )
        return root
    else:
        # get radio station for type
        ws_resp = ais_cloud_ws.audio_name(
            ais_global.G_AN_RADIO, media_content_id.replace("ais_radio/", "")
        )
        json_ws_resp = ws_resp.json()
        ais_radio_stations = []
        for item in json_ws_resp["data"]:
            ais_radio_stations.append(
                BrowseMedia(
                    title=item["NAME"],
                    media_class=MEDIA_CLASS_MUSIC,
                    media_content_id=item["STREAM_URL"],
                    media_content_type=MEDIA_TYPE_MUSIC,
                    can_play=True,
                    can_expand=False,
                    thumbnail=item["IMAGE_URL"],
                )
            )
        root = BrowseMedia(
            title=media_content_id.replace("ais_radio/", ""),
            media_class=MEDIA_CLASS_PLAYLIST,
            media_content_id=media_content_id,
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            thumbnail="http://www.ai-speaker.com/images/media-browser/radio.svg",
            children=ais_radio_stations,
        )
        return root


def ais_bookmarks_library(hass) -> BrowseMedia:
    d = hass.data["ais_bookmarks"]
    ais_bookmarks = []
    for bookmark in reversed(d.bookmarks):
        if (
            "media_stream_image" in bookmark
            and bookmark["media_stream_image"] is not None
        ):
            img = bookmark["media_stream_image"]
        else:
            img = "/static/icons/tile-win-310x150.png"
        if bookmark["name"].startswith(bookmark["source"]):
            name = bookmark["name"]
        else:
            name = (
                ais_global.G_NAME_FOR_AUDIO_NATURE.get(
                    bookmark["source"], bookmark["source"]
                )
                + " "
                + bookmark["name"]
            )

        ais_bookmarks.append(
            BrowseMedia(
                title=name,
                media_class=MEDIA_CLASS_MUSIC,
                media_content_id=bookmark["media_content_id"],
                media_content_type=MEDIA_TYPE_MUSIC,
                can_play=True,
                can_expand=False,
                thumbnail=img,
            )
        )

    root = BrowseMedia(
        title="Zakładki",
        media_class=MEDIA_CLASS_PLAYLIST,
        media_content_id="ais_bookmarks",
        media_content_type=MEDIA_TYPE_APP,
        can_expand=True,
        can_play=False,
        thumbnail="http://www.ai-speaker.com/images/media-browser/bookmarks.svg",
        children=ais_bookmarks,
    )

    return root


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
