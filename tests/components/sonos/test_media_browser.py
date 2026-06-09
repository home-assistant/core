"""Tests for the Sonos Media Browser."""

from functools import partial
from unittest.mock import MagicMock, Mock, patch
from urllib.parse import quote

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.components.sonos.const import MEDIA_TYPE_DIRECTORY, SONOS_TRACKS
from homeassistant.components.sonos.media_browser import (
    build_item_response,
    get_media,
    get_thumbnail_url_full,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import MockMusicServiceItem, SoCoMockFactory

from tests.typing import WebSocketGenerator


def mock_browse_by_idstring(
    search_type: str, idstring: str, start=0, max_items=100, full_album_art_uri=False
) -> list[MockMusicServiceItem]:
    """Mock the call to browse_by_id_string."""
    if search_type == "albums" and idstring in (
        "A:ALBUM/Abbey%20Road",
        "A:ALBUM/Abbey Road",
    ):
        return [
            MockMusicServiceItem(
                "Come Together",
                "S://192.168.42.10/music/The%20Beatles/Abbey%20Road/01%20Come%20Together.mp3",
                "A:ALBUM/Abbey%20Road",
                "object.item.audioItem.musicTrack",
            ),
            MockMusicServiceItem(
                "Something",
                "S://192.168.42.10/music/The%20Beatles/Abbey%20Road/03%20Something.mp3",
                "A:ALBUM/Abbey%20Road",
                "object.item.audioItem.musicTrack",
            ),
        ]
    return None


async def test_build_item_response(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    async_autosetup_sonos,
    soco,
    discover,
) -> None:
    """Test building a browse item response."""
    soco_mock = soco_factory.mock_list.get("192.168.42.2")
    soco_mock.music_library.browse_by_idstring = mock_browse_by_idstring
    browse_item: BrowseMedia = build_item_response(
        soco_mock.music_library,
        {"search_type": MediaType.ALBUM, "idstring": "A:ALBUM/Abbey%20Road"},
        partial(
            get_thumbnail_url_full,
            soco_mock.music_library,
            True,
            None,
        ),
    )
    assert browse_item.title == "Abbey Road"
    assert browse_item.media_class == MediaClass.ALBUM
    assert browse_item.media_content_id == "A:ALBUM/Abbey%20Road"
    assert len(browse_item.children) == 2
    assert browse_item.children[0].media_class == MediaClass.TRACK
    assert browse_item.children[0].title == "Come Together"
    assert (
        browse_item.children[0].media_content_id
        == "x-file-cifs://192.168.42.10/music/The%20Beatles/Abbey%20Road/01%20Come%20Together.mp3"
    )
    assert browse_item.children[1].media_class == MediaClass.TRACK
    assert browse_item.children[1].title == "Something"
    assert (
        browse_item.children[1].media_content_id
        == "x-file-cifs://192.168.42.10/music/The%20Beatles/Abbey%20Road/03%20Something.mp3"
    )


def test_get_media_multisegment_album_id_uses_album_segment() -> None:
    """Test `A:ALBUM/<album>/<artist>` uses album name as lookup search term."""
    music_library = MagicMock()
    music_library.get_music_library_information.return_value = []
    result = get_media(
        music_library,
        "A:ALBUM/Abbey%20Road/The%20Beatles",
        "album",
    )

    assert result is None
    assert music_library.get_music_library_information.call_count == 1
    assert music_library.get_music_library_information.call_args.args == ("albums",)
    assert music_library.get_music_library_information.call_args.kwargs == {
        "search_term": "Abbey Road",
        "full_album_art_uri": True,
    }


def test_get_media_multisegment_album_id_prefers_exact_item_id_match() -> None:
    """Test multi-match disambiguation prefers exact `item_id`."""
    music_library = MagicMock()
    exact_item = MockMusicServiceItem(
        "Abbey Road (Remaster)",
        "A:ALBUM/Abbey%20Road/The%20Beatles",
        "A:ALBUM",
        "object.container.album.musicAlbum",
    )
    music_library.get_music_library_information.return_value = [
        MockMusicServiceItem(
            "Abbey Road",
            "A:ALBUM/Abbey%20Road/Someone%20Else",
            "A:ALBUM",
            "object.container.album.musicAlbum",
        ),
        exact_item,
    ]

    result = get_media(
        music_library,
        "A:ALBUM/Abbey%20Road/The%20Beatles",
        "album",
    )

    assert result is exact_item


def test_get_media_multisegment_album_id_falls_back_to_exact_title_match() -> None:
    """Test multi-match disambiguation falls back to exact title match."""
    music_library = MagicMock()
    title_match_item = MockMusicServiceItem(
        "Abbey Road",
        "A:ALBUM/Abbey%20Road/The%20Beatles%20(Remaster)",
        "A:ALBUM",
        "object.container.album.musicAlbum",
    )
    music_library.get_music_library_information.return_value = [
        MockMusicServiceItem(
            "Abbey Road (Live)",
            "A:ALBUM/Abbey%20Road/The%20Beatles%20(Live)",
            "A:ALBUM",
            "object.container.album.musicAlbum",
        ),
        title_match_item,
    ]

    result = get_media(
        music_library,
        "A:ALBUM/Abbey%20Road/The%20Beatles",
        "album",
    )

    assert result is title_match_item


async def test_browse_media_root(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    async_autosetup_sonos,
    soco,
    discover,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the async_browse_media method."""

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.zone_a",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["children"] == snapshot


async def test_browse_media_library(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    async_autosetup_sonos,
    soco,
    discover,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the async_browse_media method."""

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.zone_a",
            "media_content_id": "",
            "media_content_type": "library",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["children"] == snapshot


async def test_browse_media_library_albums(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    async_autosetup_sonos,
    soco,
    discover,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the async_browse_media method."""
    soco_mock = soco_factory.mock_list.get("192.168.42.2")

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.zone_a",
            "media_content_id": "A:ALBUM",
            "media_content_type": "album",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["children"] == snapshot
    assert soco_mock.music_library.browse_by_idstring.call_count == 1


@pytest.mark.parametrize(
    ("media_content_id", "media_content_type"),
    [
        (
            "",
            "favorites",
        ),
        (
            "object.item.audioItem.audioBook",
            "favorites_folder",
        ),
        (
            "object.container.album.musicAlbum",
            "favorites_folder",
        ),
        (
            "object.container.podcast",
            "favorites_folder",
        ),
    ],
)
async def test_browse_media_favorites(
    async_autosetup_sonos,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    media_content_id,
    media_content_type,
) -> None:
    """Test the async_browse_media method."""
    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.zone_a",
            "media_content_id": media_content_id,
            "media_content_type": media_content_type,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == snapshot


@pytest.mark.parametrize(
    "media_content_id",
    [
        ("S:"),
        ("S://192.168.1.1/music"),
    ],
)
async def test_browse_media_library_folders(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    async_autosetup_sonos,
    media_content_id: str,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the async_browse_media method."""
    soco_mock = soco_factory.mock_list.get("192.168.42.2")

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            ATTR_ENTITY_ID: "media_player.zone_a",
            ATTR_MEDIA_CONTENT_ID: media_content_id,
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_DIRECTORY,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == snapshot
    assert soco_mock.music_library.browse_by_idstring.call_count == 1


async def test_search_media(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    async_autosetup_sonos,
    soco,
    discover,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the async_search_media method returns tracks matching the query."""
    soco_mock = soco_factory.mock_list.get("192.168.42.2")
    mock_items = [
        MockMusicServiceItem(
            "Come Together",
            "S://192.168.42.10/music/The%20Beatles/Abbey%20Road/01%20Come%20Together.mp3",
            "A:ALBUM/Abbey%20Road",
            "object.item.audioItem.musicTrack",
            album_art_uri="http://example.com/abbey_road.jpg",
        ),
        MockMusicServiceItem(
            "Something",
            "S://192.168.42.10/music/The%20Beatles/Abbey%20Road/03%20Something.mp3",
            "A:ALBUM/Abbey%20Road",
            "object.item.audioItem.musicTrack",
            album_art_uri="http://example.com/abbey_road.jpg",
        ),
    ]
    soco_mock.music_library.get_music_library_information = Mock(
        return_value=mock_items
    )

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/search_media",
            "entity_id": "media_player.zone_a",
            "search_query": "Come Together",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    assert response["result"] == snapshot

    assert soco_mock.music_library.get_music_library_information.call_args.args == (
        SONOS_TRACKS,
    )
    assert soco_mock.music_library.get_music_library_information.call_args.kwargs == {
        "search_term": "Come Together",
        "full_album_art_uri": True,
        "complete_result": True,
    }


async def test_search_media_invalid_media_content_type(
    hass: HomeAssistant,
    async_autosetup_sonos,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that async_search_media raises on an unsupported media_content_type."""
    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/search_media",
            "entity_id": "media_player.zone_a",
            "media_content_type": "movie",
            "media_content_id": "some_id",
            "search_query": "test",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert response["error"]["translation_key"] == "invalid_media_content_type"
    assert response["error"]["translation_placeholders"] == {
        "media_content_type": "movie"
    }


def test_get_thumbnail_url_full_caches_track_art() -> None:
    """Test a non-internal browse caches the item's art URI without decoding the URL.

    The proxy URL must not be unquoted: get_browse_image_url percent-encodes the
    content id into the path, and a track URI's "?sid=...&..." query string would
    otherwise collapse into the proxy URL and truncate the id.
    """
    media = Mock()
    media.browse_image_uris = {}
    track_uri = "x-sonos-spotify:spotify%3atrack%3a5bcTCx?sid=12&flags=8224&sn=3"
    item = MockMusicServiceItem(
        "Come Together",
        track_uri,
        "playlist",
        "object.item.audioItem.musicTrack",
        album_art_uri="http://192.168.42.2:1400/getaa?u=track&v=1",
    )
    proxy_url = (
        "/api/media_player_proxy/media_player.zone_a/browse_media/track/"
        + quote(track_uri)
        + "?token=abc"
    )
    get_browse_image_url = Mock(return_value=proxy_url)

    result = get_thumbnail_url_full(
        media,
        False,
        get_browse_image_url,
        MediaType.TRACK,
        track_uri,
        None,
        item,
    )

    assert media.browse_image_uris[track_uri] == item.album_art_uri
    assert result == proxy_url


def test_get_thumbnail_url_full_skips_non_track_cache() -> None:
    """Test only track art is cached; albums and artists resolve via get_media."""
    media = Mock()
    media.browse_image_uris = {}
    content_id = "A:ALBUM/Abbey%20Road"
    item = MockMusicServiceItem(
        "Abbey Road",
        content_id,
        "A:ALBUM",
        "object.container.album.musicAlbum",
        album_art_uri="http://192.168.42.2:1400/getaa?u=album&v=1",
    )
    get_browse_image_url = Mock(return_value="/proxy/album")

    get_thumbnail_url_full(
        media,
        False,
        get_browse_image_url,
        MediaType.ALBUM,
        content_id,
        None,
        item,
    )

    assert media.browse_image_uris == {}


async def test_browse_image_for_track_uses_cached_art(
    hass: HomeAssistant,
    async_autosetup_sonos,
) -> None:
    """Test a track's browse image is served from the art URI captured at browse time."""
    entity_comp = hass.data["entity_components"]["media_player"]
    player = entity_comp.get_entity("media_player.zone_a")
    track_uri = "x-sonos-spotify:spotify%3atrack%3a5bcTCx?sid=12&flags=8224&sn=3"
    art_url = "http://192.168.42.2:1400/getaa?u=track&v=1"
    player.media.browse_image_uris[track_uri] = art_url

    with patch.object(
        player, "_async_fetch_image", return_value=(b"image", "image/jpeg")
    ) as mock_fetch:
        result = await player.async_get_browse_image(MediaType.TRACK, track_uri)

    assert result == (b"image", "image/jpeg")
    mock_fetch.assert_awaited_once_with(art_url)
