"""Support for media browsing."""
import asyncio
import contextlib
import logging

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
)

PLAYABLE_MEDIA_TYPES = [
    MediaType.ALBUM,
    MediaType.ARTIST,
    MediaType.TRACK,
]

CONTAINER_TYPES_SPECIFIC_MEDIA_CLASS = {
    MediaType.ALBUM: MediaClass.ALBUM,
    MediaType.ARTIST: MediaClass.ARTIST,
    MediaType.PLAYLIST: MediaClass.PLAYLIST,
    MediaType.SEASON: MediaClass.SEASON,
    MediaType.TVSHOW: MediaClass.TV_SHOW,
}

CHILD_TYPE_MEDIA_CLASS = {
    MediaType.SEASON: MediaClass.SEASON,
    MediaType.ALBUM: MediaClass.ALBUM,
    MediaType.ARTIST: MediaClass.ARTIST,
    MediaType.MOVIE: MediaClass.MOVIE,
    MediaType.PLAYLIST: MediaClass.PLAYLIST,
    MediaType.TRACK: MediaClass.TRACK,
    MediaType.TVSHOW: MediaClass.TV_SHOW,
    MediaType.CHANNEL: MediaClass.CHANNEL,
    MediaType.EPISODE: MediaClass.EPISODE,
}

_LOGGER = logging.getLogger(__name__)


class UnknownMediaType(BrowseError):
    """Unknown media type."""


async def build_item_response(media_library, payload, get_thumbnail_url=None):
    """Create response payload for the provided media query."""
    search_id = payload["search_id"]
    search_type = payload["search_type"]

    _, title, media = await get_media_info(media_library, search_id, search_type)
    thumbnail = await get_thumbnail_url(search_type, search_id)

    if media is None:
        return None

    children = await asyncio.gather(
        *(item_payload(item, get_thumbnail_url) for item in media)
    )

    if search_type in (MediaType.TVSHOW, MediaType.MOVIE) and search_id == "":
        children.sort(key=lambda x: x.title.replace("The ", "", 1), reverse=False)

    response = BrowseMedia(
        media_class=CONTAINER_TYPES_SPECIFIC_MEDIA_CLASS.get(
            search_type, MediaClass.DIRECTORY
        ),
        media_content_id=search_id,
        media_content_type=search_type,
        title=title,
        can_play=search_type in PLAYABLE_MEDIA_TYPES and search_id,
        can_expand=True,
        children=children,
        thumbnail=thumbnail,
    )

    if search_type == "library_music":
        response.children_media_class = MediaClass.MUSIC
    else:
        response.calculate_children_class()

    return response


async def item_payload(item, get_thumbnail_url=None):
    """Create response payload for a single media item.

    Used by async_browse_media.
    """
    title = item["label"]

    media_class = None

    if "songid" in item:
        media_content_type = MediaType.TRACK
        media_content_id = f"{item['songid']}"
        can_play = True
        can_expand = False
    elif "albumid" in item:
        media_content_type = MediaType.ALBUM
        media_content_id = f"{item['albumid']}"
        can_play = True
        can_expand = True
    elif "artistid" in item:
        media_content_type = MediaType.ARTIST
        media_content_id = f"{item['artistid']}"
        can_play = True
        can_expand = True
    elif "movieid" in item:
        media_content_type = MediaType.MOVIE
        media_content_id = f"{item['movieid']}"
        can_play = True
        can_expand = False
    elif "episodeid" in item:
        media_content_type = MediaType.EPISODE
        media_content_id = f"{item['episodeid']}"
        can_play = True
        can_expand = False
    elif "seasonid" in item:
        media_content_type = MediaType.SEASON
        media_content_id = f"{item['tvshowid']}/{item['season']}"
        can_play = False
        can_expand = True
    elif "tvshowid" in item:
        media_content_type = MediaType.TVSHOW
        media_content_id = f"{item['tvshowid']}"
        can_play = False
        can_expand = True
    elif "channelid" in item:
        media_content_type = MediaType.CHANNEL
        media_content_id = f"{item['channelid']}"
        if broadcasting := item.get("broadcastnow"):
            show = broadcasting.get("title")
            title = f"{title} - {show}"
        can_play = True
        can_expand = False
    else:
        # this case is for the top folder of each type
        # possible content types: album, artist, movie, library_music, tvshow, channel
        media_class = MediaClass.DIRECTORY
        media_content_type = item["type"]
        media_content_id = ""
        can_play = False
        can_expand = True

    if media_class is None:
        try:
            media_class = CHILD_TYPE_MEDIA_CLASS[media_content_type]
        except KeyError as err:
            _LOGGER.debug("Unknown media type received: %s", media_content_type)
            raise UnknownMediaType from err

    thumbnail = item.get("thumbnail")
    if thumbnail is not None and get_thumbnail_url is not None:
        thumbnail = await get_thumbnail_url(
            media_content_type, media_content_id, thumbnail_url=thumbnail
        )

    return BrowseMedia(
        title=title,
        media_class=media_class,
        media_content_type=media_content_type,
        media_content_id=media_content_id,
        can_play=can_play,
        can_expand=can_expand,
        thumbnail=thumbnail,
    )


def media_source_content_filter(item: BrowseMedia) -> bool:
    """Content filter for media sources."""
    # Filter out cameras using PNG over MJPEG. They don't work in Kodi.
    return not (
        item.media_content_id.startswith("media-source://camera/")
        and item.media_content_type == "image/png"
    )


async def library_payload(hass):
    """Create response payload to describe contents of a specific library.

    Used by async_browse_media.
    """
    library_info = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="library",
        media_content_type="library",
        title="Media Library",
        can_play=False,
        can_expand=True,
        children=[],
    )

    library = {
        "library_music": "Music",
        MediaType.MOVIE: "Movies",
        MediaType.TVSHOW: "TV shows",
        MediaType.CHANNEL: "Channels",
    }

    library_info.children = await asyncio.gather(
        *(
            item_payload(
                {
                    "label": item["label"],
                    "type": item["type"],
                    "uri": item["type"],
                },
            )
            for item in [
                {"label": name, "type": type_} for type_, name in library.items()
            ]
        )
    )

    for child in library_info.children:
        child.thumbnail = "https://brands.home-assistant.io/_/kodi/logo.png"

    with contextlib.suppress(media_source.BrowseError):
        item = await media_source.async_browse_media(
            hass, None, content_filter=media_source_content_filter
        )
        # If domain is None, it's overview of available sources
        if item.domain is None:
            library_info.children.extend(item.children)
        else:
            library_info.children.append(item)

    return library_info


async def get_media_info(media_library, search_id, search_type):
    """Fetch media/album."""
    thumbnail = None
    title = None
    media = None

    properties = ["thumbnail"]
    if search_type == MediaType.ALBUM:
        if search_id:
            album = await media_library.get_album_details(
                album_id=int(search_id), properties=properties
            )
            thumbnail = media_library.thumbnail_url(
                album["albumdetails"].get("thumbnail")
            )
            title = album["albumdetails"]["label"]
            media = await media_library.get_songs(
                album_id=int(search_id),
                properties=[
                    "albumid",
                    "artist",
                    "duration",
                    "album",
                    "thumbnail",
                    "track",
                ],
            )
            media = media.get("songs")
        else:
            media = await media_library.get_albums(properties=properties)
            media = media.get("albums")
            title = "Albums"

    elif search_type == MediaType.ARTIST:
        if search_id:
            media = await media_library.get_albums(
                artist_id=int(search_id), properties=properties
            )
            media = media.get("albums")
            artist = await media_library.get_artist_details(
                artist_id=int(search_id), properties=properties
            )
            thumbnail = media_library.thumbnail_url(
                artist["artistdetails"].get("thumbnail")
            )
            title = artist["artistdetails"]["label"]
        else:
            media = await media_library.get_artists(properties)
            media = media.get("artists")
            title = "Artists"

    elif search_type == "library_music":
        library = {MediaType.ALBUM: "Albums", MediaType.ARTIST: "Artists"}
        media = [{"label": name, "type": type_} for type_, name in library.items()]
        title = "Music Library"

    elif search_type == MediaType.MOVIE:
        if search_id:
            movie = await media_library.get_movie_details(
                movie_id=int(search_id), properties=properties
            )
            thumbnail = media_library.thumbnail_url(
                movie["moviedetails"].get("thumbnail")
            )
            title = movie["moviedetails"]["label"]
        else:
            media = await media_library.get_movies(properties)
            media = media.get("movies")
            title = "Movies"

    elif search_type == MediaType.TVSHOW:
        if search_id:
            media = await media_library.get_seasons(
                tv_show_id=int(search_id),
                properties=["thumbnail", "season", "tvshowid"],
            )
            media = media.get("seasons")
            tvshow = await media_library.get_tv_show_details(
                tv_show_id=int(search_id), properties=properties
            )
            thumbnail = media_library.thumbnail_url(
                tvshow["tvshowdetails"].get("thumbnail")
            )
            title = tvshow["tvshowdetails"]["label"]
        else:
            media = await media_library.get_tv_shows(properties)
            media = media.get("tvshows")
            title = "TV Shows"

    elif search_type == MediaType.SEASON:
        tv_show_id, season_id = search_id.split("/", 1)
        media = await media_library.get_episodes(
            tv_show_id=int(tv_show_id),
            season_id=int(season_id),
            properties=["thumbnail", "tvshowid", "seasonid"],
        )
        media = media.get("episodes")
        if media:
            season = await media_library.get_season_details(
                season_id=int(media[0]["seasonid"]), properties=properties
            )
            thumbnail = media_library.thumbnail_url(
                season["seasondetails"].get("thumbnail")
            )
            title = season["seasondetails"]["label"]

    elif search_type == MediaType.CHANNEL:
        media = await media_library.get_channels(
            channel_group_id="alltv",
            properties=["thumbnail", "channeltype", "channel", "broadcastnow"],
        )
        media = media.get("channels")
        title = "Channels"

    return thumbnail, title, media
