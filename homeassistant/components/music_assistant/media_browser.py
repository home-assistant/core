"""Media Source Implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from music_assistant_models.media_items import MediaItemType

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.core import HomeAssistant

from .const import DEFAULT_NAME, DOMAIN

if TYPE_CHECKING:
    from music_assistant_client import MusicAssistantClient

MEDIA_TYPE_RADIO = "radio"
MEDIA_TYPE_PODCAST_EPISODE = "podcast_episode"
MEDIA_TYPE_AUDIOBOOK = "audiobook"

PLAYABLE_MEDIA_TYPES = [
    MediaType.PLAYLIST,
    MediaType.ALBUM,
    MediaType.ARTIST,
    MEDIA_TYPE_RADIO,
    MediaType.PODCAST,
    MEDIA_TYPE_AUDIOBOOK,
    MediaType.TRACK,
]

LIBRARY_ARTISTS = "artists"
LIBRARY_ALBUMS = "albums"
LIBRARY_TRACKS = "tracks"
LIBRARY_PLAYLISTS = "playlists"
LIBRARY_RADIO = "radio"
LIBRARY_PODCASTS = "podcasts"
LIBRARY_AUDIOBOOKS = "audiobooks"


LIBRARY_TITLE_MAP = {
    LIBRARY_ARTISTS: "Artists",
    LIBRARY_ALBUMS: "Albums",
    LIBRARY_TRACKS: "Tracks",
    LIBRARY_PLAYLISTS: "Playlists",
    LIBRARY_RADIO: "Radio stations",
    LIBRARY_PODCASTS: "Podcasts",
    LIBRARY_AUDIOBOOKS: "Audiobooks",
}

LIBRARY_MEDIA_CLASS_MAP = {
    LIBRARY_ARTISTS: MediaClass.ARTIST,
    LIBRARY_ALBUMS: MediaClass.ALBUM,
    LIBRARY_TRACKS: MediaClass.TRACK,
    LIBRARY_PLAYLISTS: MediaClass.PLAYLIST,
    LIBRARY_RADIO: MediaClass.MUSIC,  # radio is not accepted by HA
    LIBRARY_PODCASTS: MediaClass.PODCAST,
    LIBRARY_AUDIOBOOKS: MediaClass.DIRECTORY,  # audiobook is not accepted by HA
}

MEDIA_CONTENT_TYPE_FLAC = "audio/flac"
THUMB_SIZE = 200
SORT_NAME_DESC = "sort_name_desc"


def media_source_filter(item: BrowseMedia) -> bool:
    """Filter media sources."""
    return item.media_content_type.startswith("audio/")


async def async_browse_media(
    hass: HomeAssistant,
    mass: MusicAssistantClient,
    media_content_id: str | None,
    media_content_type: str | None,
) -> BrowseMedia:
    """Browse media."""
    if media_content_id is None:
        return await build_main_listing(hass)

    assert media_content_type is not None

    if media_source.is_media_source_id(media_content_id):
        return await media_source.async_browse_media(
            hass, media_content_id, content_filter=media_source_filter
        )

    if media_content_id == LIBRARY_ARTISTS:
        return await build_artists_listing(mass)
    if media_content_id == LIBRARY_ALBUMS:
        return await build_albums_listing(mass)
    if media_content_id == LIBRARY_TRACKS:
        return await build_tracks_listing(mass)
    if media_content_id == LIBRARY_PLAYLISTS:
        return await build_playlists_listing(mass)
    if media_content_id == LIBRARY_RADIO:
        return await build_radio_listing(mass)
    if media_content_id == LIBRARY_PODCASTS:
        return await build_podcasts_listing(mass)
    if media_content_id == LIBRARY_AUDIOBOOKS:
        return await build_audiobooks_listing(mass)
    if "artist" in media_content_id:
        return await build_artist_items_listing(mass, media_content_id)
    if "album" in media_content_id:
        return await build_album_items_listing(mass, media_content_id)
    if "playlist" in media_content_id:
        return await build_playlist_items_listing(mass, media_content_id)
    raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")


async def build_main_listing(hass: HomeAssistant) -> BrowseMedia:
    """Build main browse listing."""
    children: list[BrowseMedia] = []
    for library, media_class in LIBRARY_MEDIA_CLASS_MAP.items():
        child_source = BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id=library,
            media_content_type=DOMAIN,
            title=LIBRARY_TITLE_MAP[library],
            children_media_class=media_class,
            can_play=False,
            can_expand=True,
        )
        children.append(child_source)

    try:
        item = await media_source.async_browse_media(
            hass, None, content_filter=media_source_filter
        )
        # If domain is None, it's overview of available sources
        if item.domain is None and item.children is not None:
            children.extend(item.children)
        else:
            children.append(item)
    except media_source.BrowseError:
        pass

    return BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type=DOMAIN,
        title=DEFAULT_NAME,
        can_play=False,
        can_expand=True,
        children=children,
    )


async def build_playlists_listing(mass: MusicAssistantClient) -> BrowseMedia:
    """Build Playlists browse listing."""
    media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_PLAYLISTS]
    return BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id=LIBRARY_PLAYLISTS,
        media_content_type=MediaType.PLAYLIST,
        title=LIBRARY_TITLE_MAP[LIBRARY_PLAYLISTS],
        can_play=False,
        can_expand=True,
        children_media_class=media_class,
        children=[
            build_item(mass, item, can_expand=True)
            # we only grab the first page here because the
            # HA media browser does not support paging
            for item in await mass.music.get_library_playlists(
                limit=500, order_by=SORT_NAME_DESC
            )
            if item.available
        ],
    )


async def build_playlist_items_listing(
    mass: MusicAssistantClient, identifier: str
) -> BrowseMedia:
    """Build Playlist items browse listing."""
    playlist = await mass.music.get_item_by_uri(identifier)
    if TYPE_CHECKING:
        assert playlist.uri is not None

    return BrowseMedia(
        media_class=MediaClass.PLAYLIST,
        media_content_id=playlist.uri,
        media_content_type=MediaType.PLAYLIST,
        title=playlist.name,
        can_play=True,
        can_expand=True,
        children_media_class=MediaClass.TRACK,
        children=[
            build_item(mass, item, can_expand=False)
            # we only grab the first page here because the
            # HA media browser does not support paging
            for item in await mass.music.get_playlist_tracks(
                playlist.item_id, playlist.provider
            )
            if item.available
        ],
    )


async def build_artists_listing(mass: MusicAssistantClient) -> BrowseMedia:
    """Build Albums browse listing."""
    media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_ARTISTS]

    return BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id=LIBRARY_ARTISTS,
        media_content_type=MediaType.ARTIST,
        title=LIBRARY_TITLE_MAP[LIBRARY_ARTISTS],
        can_play=False,
        can_expand=True,
        children_media_class=media_class,
        children=[
            build_item(mass, artist, can_expand=True)
            # we only grab the first page here because the
            # HA media browser does not support paging
            for artist in await mass.music.get_library_artists(
                limit=500, order_by=SORT_NAME_DESC
            )
            if artist.available
        ],
    )


async def build_artist_items_listing(
    mass: MusicAssistantClient, identifier: str
) -> BrowseMedia:
    """Build Artist items browse listing."""
    artist = await mass.music.get_item_by_uri(identifier)
    albums = await mass.music.get_artist_albums(artist.item_id, artist.provider)

    if TYPE_CHECKING:
        assert artist.uri is not None

    return BrowseMedia(
        media_class=MediaType.ARTIST,
        media_content_id=artist.uri,
        media_content_type=MediaType.ARTIST,
        title=artist.name,
        can_play=True,
        can_expand=True,
        children_media_class=MediaClass.ALBUM,
        children=[
            build_item(mass, album, can_expand=True)
            for album in albums
            if album.available
        ],
    )


async def build_albums_listing(mass: MusicAssistantClient) -> BrowseMedia:
    """Build Albums browse listing."""
    media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_ALBUMS]

    return BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id=LIBRARY_ALBUMS,
        media_content_type=MediaType.ALBUM,
        title=LIBRARY_TITLE_MAP[LIBRARY_ALBUMS],
        can_play=False,
        can_expand=True,
        children_media_class=media_class,
        children=[
            build_item(mass, album, can_expand=True)
            # we only grab the first page here because the
            # HA media browser does not support paging
            for album in await mass.music.get_library_albums(
                limit=500, order_by=SORT_NAME_DESC
            )
            if album.available
        ],
    )


async def build_album_items_listing(
    mass: MusicAssistantClient, identifier: str
) -> BrowseMedia:
    """Build Album items browse listing."""
    album = await mass.music.get_item_by_uri(identifier)
    tracks = await mass.music.get_album_tracks(album.item_id, album.provider)

    if TYPE_CHECKING:
        assert album.uri is not None

    return BrowseMedia(
        media_class=MediaType.ALBUM,
        media_content_id=album.uri,
        media_content_type=MediaType.ALBUM,
        title=album.name,
        can_play=True,
        can_expand=True,
        children_media_class=MediaClass.TRACK,
        children=[
            build_item(mass, track, False) for track in tracks if track.available
        ],
    )


async def build_tracks_listing(mass: MusicAssistantClient) -> BrowseMedia:
    """Build Tracks browse listing."""
    media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_TRACKS]

    return BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id=LIBRARY_TRACKS,
        media_content_type=MediaType.TRACK,
        title=LIBRARY_TITLE_MAP[LIBRARY_TRACKS],
        can_play=False,
        can_expand=True,
        children_media_class=media_class,
        children=[
            build_item(mass, track, can_expand=False)
            # we only grab the first page here because the
            # HA media browser does not support paging
            for track in await mass.music.get_library_tracks(
                limit=500, order_by=SORT_NAME_DESC
            )
            if track.available
        ],
    )


async def build_podcasts_listing(mass: MusicAssistantClient) -> BrowseMedia:
    """Build Podcasts browse listing."""
    media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_PODCASTS]
    return BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id=LIBRARY_PODCASTS,
        media_content_type=MediaType.PODCAST,
        title=LIBRARY_TITLE_MAP[LIBRARY_PODCASTS],
        can_play=False,
        can_expand=True,
        children_media_class=media_class,
        children=[
            build_item(mass, podcast, can_expand=False)
            # we only grab the first page here because the
            # HA media browser does not support paging
            for podcast in await mass.music.get_library_podcasts(
                limit=500, order_by=SORT_NAME_DESC
            )
            if podcast.available
        ],
    )


async def build_audiobooks_listing(mass: MusicAssistantClient) -> BrowseMedia:
    """Build Audiobooks browse listing."""
    media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_AUDIOBOOKS]
    return BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id=LIBRARY_AUDIOBOOKS,
        media_content_type=DOMAIN,
        title=LIBRARY_TITLE_MAP[LIBRARY_AUDIOBOOKS],
        can_play=False,
        can_expand=True,
        children_media_class=media_class,
        children=[
            build_item(mass, audiobook, can_expand=False)
            # we only grab the first page here because the
            # HA media browser does not support paging
            for audiobook in await mass.music.get_library_audiobooks(
                limit=500, order_by=SORT_NAME_DESC
            )
            if audiobook.available
        ],
    )


async def build_radio_listing(mass: MusicAssistantClient) -> BrowseMedia:
    """Build Radio browse listing."""
    media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_RADIO]
    return BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id=LIBRARY_RADIO,
        media_content_type=DOMAIN,
        title=LIBRARY_TITLE_MAP[LIBRARY_RADIO],
        can_play=False,
        can_expand=True,
        children_media_class=media_class,
        children=[
            build_item(mass, track, can_expand=False, media_class=media_class)
            # we only grab the first page here because the
            # HA media browser does not support paging
            for track in await mass.music.get_library_radios(
                limit=500, order_by=SORT_NAME_DESC
            )
            if track.available
        ],
    )


def build_item(
    mass: MusicAssistantClient,
    item: MediaItemType,
    can_expand: bool = True,
    media_class: Any = None,
) -> BrowseMedia:
    """Return BrowseMedia for MediaItem."""
    if artists := getattr(item, "artists", None):
        title = f"{artists[0].name} - {item.name}"
    else:
        title = item.name
    img_url = mass.get_media_item_image_url(item)

    if TYPE_CHECKING:
        assert item.uri is not None

    return BrowseMedia(
        media_class=media_class or item.media_type.value,
        media_content_id=item.uri,
        media_content_type=MediaType.MUSIC,
        title=title,
        can_play=True,
        can_expand=can_expand,
        thumbnail=img_url,
    )
