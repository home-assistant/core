"""Tests for the Kodi media browser."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.kodi.browse_media import (
    build_item_response,
    get_media_info,
)
from homeassistant.components.media_player import MediaType

CHANNELS = {
    "channels": [
        {
            "channelid": 917,
            "label": "Das Erste HD",
            "thumbnail": "image://pvrchannel_tv%40das_erste/",
        },
        {
            "channelid": 902,
            "label": "ZDF HD",
            "thumbnail": "image://pvrchannel_tv%40zdf/",
        },
        {
            "channelid": 850,
            "label": "3sat HD",
        },
    ]
}


def create_media_library() -> MagicMock:
    """Return a Kodi library that answers with the TV channels above."""
    library = MagicMock()
    library.get_channels = AsyncMock(return_value=CHANNELS)
    library.thumbnail_url = MagicMock(
        side_effect=lambda thumbnail: (
            f"http://1.1.1.1:8080/image/{thumbnail}" if thumbnail else None
        )
    )
    return library


async def test_channel_folder_lists_the_channels() -> None:
    """The folder itself is listed and has no thumbnail of its own."""
    library = create_media_library()

    thumbnail, title, media = await get_media_info(library, "", MediaType.CHANNEL)

    assert title == "Channels"
    assert media == CHANNELS["channels"]
    assert thumbnail is None


async def test_channel_asked_for_by_id_carries_its_thumbnail() -> None:
    """A single channel returns the image the media player proxy serves.

    An external client fetches a browse thumbnail over
    /api/media_player_proxy/<entity>/browse_media/channel/<id>, which asks the
    integration for the image by id. Without this the view answers 404.
    """
    library = create_media_library()

    thumbnail, _, _ = await get_media_info(library, "902", MediaType.CHANNEL)

    assert thumbnail == "http://1.1.1.1:8080/image/image://pvrchannel_tv%40zdf/"


async def test_channel_without_a_thumbnail_has_no_picture() -> None:
    """Kodi does not promise a thumbnail for every channel."""
    library = create_media_library()

    thumbnail, _, _ = await get_media_info(library, "850", MediaType.CHANNEL)

    assert thumbnail is None


async def test_channel_no_longer_in_the_group_has_no_thumbnail() -> None:
    """An id that is not in the list leaves the thumbnail unset."""
    library = create_media_library()

    thumbnail, _, _ = await get_media_info(library, "123", MediaType.CHANNEL)

    assert thumbnail is None


async def test_channel_listing_asks_for_the_epg() -> None:
    """The listing needs what it shows: the current broadcast."""
    library = create_media_library()

    await get_media_info(library, "", MediaType.CHANNEL)

    assert library.get_channels.call_args.kwargs["properties"] == [
        "thumbnail",
        "channeltype",
        "channel",
        "broadcastnow",
    ]


async def test_single_channel_asks_for_no_more_than_the_thumbnail() -> None:
    """One image needs no EPG for a hundred and fifty channels."""
    library = create_media_library()

    await get_media_info(library, "902", MediaType.CHANNEL)

    assert library.get_channels.call_args.kwargs["properties"] == ["thumbnail"]


async def test_episode_asked_for_by_id_carries_its_thumbnail() -> None:
    """An episode requested through the browse image proxy returns its art."""
    library = create_media_library()
    library.call_method = AsyncMock(
        return_value={
            "episodedetails": {
                "label": "Pilot",
                "art": {"poster": "image://episode_poster/"},
                "thumbnail": "image://episode_thumb/",
            }
        }
    )

    thumbnail, title, media = await get_media_info(library, "42", MediaType.EPISODE)

    library.call_method.assert_awaited_once_with(
        "VideoLibrary.GetEpisodeDetails",
        episodeid=42,
        properties=["thumbnail", "art"],
    )
    assert thumbnail == "http://1.1.1.1:8080/image/image://episode_poster/"
    assert title == "Pilot"
    assert media is None


async def test_track_asked_for_by_id_carries_its_thumbnail() -> None:
    """A track requested through the browse image proxy returns its art."""
    library = create_media_library()
    library.call_method = AsyncMock(
        return_value={
            "songdetails": {
                "label": "Opening Theme",
                "art": {},
                "thumbnail": "image://song_thumb/",
            }
        }
    )

    thumbnail, title, media = await get_media_info(library, "7", MediaType.TRACK)

    library.call_method.assert_awaited_once_with(
        "AudioLibrary.GetSongDetails",
        songid=7,
        properties=["thumbnail", "art"],
    )
    assert thumbnail == "http://1.1.1.1:8080/image/image://song_thumb/"
    assert title == "Opening Theme"
    assert media is None


async def test_folder_without_thumbnail_leaves_header_unset() -> None:
    """Top-level category folders do not ask for a proxy URL when they have no art."""
    library = create_media_library()
    library.get_movies = AsyncMock(
        return_value={
            "movies": [
                {
                    "movieid": 1,
                    "label": "Movie With Art",
                    "art": {"poster": "image://movie_1/"},
                },
                {
                    "movieid": 2,
                    "label": "Movie Without Art",
                    "art": {},
                },
            ]
        }
    )
    get_thumbnail_url = AsyncMock(
        side_effect=lambda content_type, content_id, thumbnail_url=None: (
            f"/api/media_player_proxy/media_player.kodi/browse_media/{content_type}/{content_id}"
        )
    )

    response = await build_item_response(
        library,
        {"search_type": MediaType.MOVIE, "search_id": ""},
        get_thumbnail_url,
    )

    assert response is not None
    assert response.thumbnail is None
    assert [child.thumbnail for child in response.children] == [
        "/api/media_player_proxy/media_player.kodi/browse_media/movie/1",
        None,
    ]


async def test_container_with_thumbnail_sets_header_url() -> None:
    """A browsed show with artwork requests its header proxy URL."""
    library = create_media_library()
    library.get_seasons = AsyncMock(
        return_value={
            "seasons": [
                {
                    "seasonid": 3,
                    "tvshowid": 10,
                    "season": 1,
                    "label": "Season 1",
                    "art": {"poster": "image://season_1/"},
                }
            ]
        }
    )
    library.get_tv_show_details = AsyncMock(
        return_value={
            "tvshowdetails": {
                "label": "Example Show",
                "art": {"poster": "image://show_10/"},
            }
        }
    )
    get_thumbnail_url = AsyncMock(
        side_effect=lambda content_type, content_id, thumbnail_url=None: (
            f"/api/media_player_proxy/media_player.kodi/browse_media/{content_type}/{content_id}"
        )
    )

    response = await build_item_response(
        library,
        {"search_type": MediaType.TVSHOW, "search_id": "10"},
        get_thumbnail_url,
    )

    assert response is not None
    assert (
        response.thumbnail
        == "/api/media_player_proxy/media_player.kodi/browse_media/tvshow/10"
    )
    assert [child.thumbnail for child in response.children] == [
        "/api/media_player_proxy/media_player.kodi/browse_media/season/10/1"
    ]
