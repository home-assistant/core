"""Tests for the Jellyfin media_player platform."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.jellyfin.const import DOMAIN
from homeassistant.components.media_player import MediaClass
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source import (
    DOMAIN as MEDIA_SOURCE_DOMAIN,
    URI_SCHEME,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import load_json_fixture

from tests.common import MockConfigEntry


async def test_resolve(
    hass: HomeAssistant,
    mock_client: MagicMock,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
) -> None:
    """Test resolving Jellyfin media items."""

    # Test resolving a track
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("track.json")

    assert await async_setup_component(hass, MEDIA_SOURCE_DOMAIN, {})
    play_media = await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}/TRACK-UUID")

    expected_url = "http://localhost/Audio/TRACK-UUID/universal?UserId=test-username,DeviceId=TEST-UUID,MaxStreamingBitrate=140000000"
    assert play_media.mime_type == "audio/flac"
    assert play_media.url == expected_url

    # Test resolving a movie
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("movie.json")

    assert await async_setup_component(hass, MEDIA_SOURCE_DOMAIN, {})
    play_media = await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}/MOVIE-UUID")

    expected_url = "http://localhost/Videos/MOVIE-UUID/stream?static=true,DeviceId=TEST-UUID,api_key=TEST-API-KEY"
    assert play_media.mime_type == "video/mp4"
    assert play_media.url == expected_url

    # Test resolving an unsupported item
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("unsupported-item.json")

    assert await async_setup_component(hass, MEDIA_SOURCE_DOMAIN, {})
    with pytest.raises(BrowseError):
        await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}/UNSUPPORTED-ITEM-UUID")


async def test_root(
    hass: HomeAssistant,
    mock_client: MagicMock,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
) -> None:
    """Test browsing the Jellyfin root."""

    assert await async_setup_component(hass, MEDIA_SOURCE_DOMAIN, {})
    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")

    expected_child_item = {
        "domain": DOMAIN,
        "identifier": "COLLECTION-FOLDER-UUID",
        "title": "COLLECTION FOLDER",
        "media_class": MediaClass.DIRECTORY.value,
        "media_content_type": "",
        "media_content_id": "media-source://jellyfin/COLLECTION-FOLDER-UUID",
        "can_play": False,
        "can_expand": True,
        "thumbnail": None,
        "children": None,
        "children_media_class": None,
        "not_shown": 0,
    }

    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == "Jellyfin"
    assert vars(browse.children[0]) == expected_child_item


async def test_tv_library(
    hass: HomeAssistant,
    mock_client: MagicMock,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
) -> None:
    """Test browsing a Jellyfin TV Library."""

    # Test browsing an empty tv library
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("tv-collection.json")
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = {"Items": []}

    assert await async_setup_component(hass, MEDIA_SOURCE_DOMAIN, {})
    browse = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/TV-COLLECTION-FOLDER-UUID"
    )

    assert browse.domain == DOMAIN
    assert browse.identifier == "TV-COLLECTION-FOLDER-UUID"
    assert browse.title == "TVShows"
    assert browse.children == []

    # Test browsing a tv library containing series
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = load_json_fixture("series-list.json")

    browse = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/TV-COLLECTION-FOLDER-UUID"
    )

    assert browse.domain == DOMAIN
    assert browse.identifier == "TV-COLLECTION-FOLDER-UUID"
    assert browse.title == "TVShows"

    expected_child_item = {
        "domain": DOMAIN,
        "identifier": "SERIES-UUID",
        "title": "SERIES",
        "media_class": MediaClass.TV_SHOW.value,
        "media_content_type": "",
        "media_content_id": "media-source://jellyfin/SERIES-UUID",
        "can_play": False,
        "can_expand": True,
        "thumbnail": None,
        "children": None,
        "children_media_class": None,
        "not_shown": 0,
    }

    assert vars(browse.children[0]) == expected_child_item

    # Test browsing a series
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("series.json")
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = load_json_fixture("seasons.json")

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/SERIES-UUID")

    assert browse.domain == DOMAIN
    assert browse.identifier == "SERIES-UUID"
    assert browse.title == "SERIES"

    expected_child_item = {
        "domain": DOMAIN,
        "identifier": "SEASON-UUID",
        "title": "SEASON",
        "media_class": MediaClass.TV_SHOW.value,
        "media_content_type": "",
        "media_content_id": "media-source://jellyfin/SEASON-UUID",
        "can_play": False,
        "can_expand": True,
        "thumbnail": None,
        "children": None,
        "children_media_class": None,
        "not_shown": 0,
    }

    assert vars(browse.children[0]) == expected_child_item

    # Test browsing a season
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("season.json")
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = load_json_fixture("episodes.json")

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/SEASON-UUID")

    assert browse.domain == DOMAIN
    assert browse.identifier == "SEASON-UUID"
    assert browse.title == "SEASON"

    expected_child_item = {
        "domain": DOMAIN,
        "identifier": "EPISODE-UUID",
        "title": "EPISODE",
        "media_class": MediaClass.EPISODE.value,
        "media_content_type": "video/mp4",
        "media_content_id": "media-source://jellyfin/EPISODE-UUID",
        "can_play": True,
        "can_expand": False,
        "thumbnail": "http://localhost/Items/EPISODE-UUID/Images/Primary.jpg",
        "children": None,
        "children_media_class": None,
        "not_shown": 0,
    }

    assert vars(browse.children[0]) == expected_child_item


async def test_movie_library(
    hass: HomeAssistant,
    mock_client: MagicMock,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
) -> None:
    """Test browsing a Jellyfin Movie Library."""

    # Test empty movie library
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("movie-collection.json")
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = {"Items": []}

    assert await async_setup_component(hass, MEDIA_SOURCE_DOMAIN, {})
    browse = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/MOVIE-COLLECTION-FOLDER-UUID"
    )

    assert browse.domain == DOMAIN
    assert browse.identifier == "MOVIE-COLLECTION-FOLDER-UUID"
    assert browse.title == "Movies"
    assert browse.children == []

    # Test browsing a movie library containing movies
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = load_json_fixture("movies.json")

    browse = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/MOVIE-COLLECTION-FOLDER-UUID"
    )

    assert browse.domain == DOMAIN
    assert browse.identifier == "MOVIE-COLLECTION-FOLDER-UUID"
    assert browse.title == "Movies"

    expected_child_item = {
        "domain": DOMAIN,
        "identifier": "MOVIE-UUID",
        "title": "MOVIE",
        "media_class": MediaClass.MOVIE.value,
        "media_content_type": "video/mp4",
        "media_content_id": "media-source://jellyfin/MOVIE-UUID",
        "can_play": True,
        "can_expand": False,
        "thumbnail": "http://localhost/Items/MOVIE-UUID/Images/Primary.jpg",
        "children": None,
        "children_media_class": None,
        "not_shown": 0,
    }

    assert vars(browse.children[0]) == expected_child_item


async def test_music_library(
    hass: HomeAssistant,
    mock_client: MagicMock,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
) -> None:
    """Test browsing a Jellyfin Music Library."""

    # Test browsinng an empty music library
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("music-collection.json")
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = {"Items": []}

    assert await async_setup_component(hass, MEDIA_SOURCE_DOMAIN, {})
    browse = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/MUSIC-COLLECTION-FOLDER-UUID"
    )

    assert browse.domain == DOMAIN
    assert browse.identifier == "MUSIC-COLLECTION-FOLDER-UUID"
    assert browse.title == "Music"
    assert browse.children == []

    # Test browsing a music library containing albums
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = load_json_fixture("albums.json")

    browse = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/MUSIC-COLLECTION-FOLDER-UUID"
    )

    assert browse.domain == DOMAIN
    assert browse.identifier == "MUSIC-COLLECTION-FOLDER-UUID"
    assert browse.title == "Music"

    expected_child_item = {
        "domain": DOMAIN,
        "identifier": "ALBUM-UUID",
        "title": "ALBUM",
        "media_class": MediaClass.ARTIST.value,
        "media_content_type": "",
        "media_content_id": "media-source://jellyfin/ALBUM-UUID",
        "can_play": False,
        "can_expand": True,
        "thumbnail": None,
        "children": None,
        "children_media_class": None,
        "not_shown": 0,
    }

    assert vars(browse.children[0]) == expected_child_item

    # Test browsing an artist
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("artist.json")
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = load_json_fixture("albums.json")

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/ARTIST-UUID")

    assert browse.domain == DOMAIN
    assert browse.identifier == "ARTIST-UUID"
    assert browse.title == "ARTIST"

    expected_child_item = {
        "domain": DOMAIN,
        "identifier": "ALBUM-UUID",
        "title": "ALBUM",
        "media_class": MediaClass.ALBUM.value,
        "media_content_type": "",
        "media_content_id": "media-source://jellyfin/ALBUM-UUID",
        "can_play": False,
        "can_expand": True,
        "thumbnail": None,
        "children": None,
        "children_media_class": None,
        "not_shown": 0,
    }

    assert vars(browse.children[0]) == expected_child_item

    # Test browsing an album
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("album.json")
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = load_json_fixture("tracks.json")

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/ALBUM-UUID")

    assert browse.domain == DOMAIN
    assert browse.identifier == "ALBUM-UUID"
    assert browse.title == "ALBUM"

    expected_child_item = {
        "domain": DOMAIN,
        "identifier": "TRACK-UUID",
        "title": "TRACK",
        "media_class": MediaClass.TRACK.value,
        "media_content_type": "audio/flac",
        "media_content_id": "media-source://jellyfin/TRACK-UUID",
        "can_play": True,
        "can_expand": False,
        "thumbnail": "http://localhost/Items/TRACK-UUID/Images/Primary.jpg",
        "children": None,
        "children_media_class": None,
        "not_shown": 0,
    }

    assert vars(browse.children[0]) == expected_child_item

    # Test browsing an album with a track with no source
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = load_json_fixture("tracks-nosource.json")

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/ALBUM-UUID")

    assert browse.domain == DOMAIN
    assert browse.identifier == "ALBUM-UUID"
    assert browse.title == "ALBUM"

    assert browse.children == []

    # Test browsing an album with a track with no path
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = load_json_fixture("tracks-nopath.json")

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/ALBUM-UUID")

    assert browse.domain == DOMAIN
    assert browse.identifier == "ALBUM-UUID"
    assert browse.title == "ALBUM"

    assert browse.children == []

    # Test browsing an album with a track with an unknown file extension
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = load_json_fixture(
        "tracks-unknown-extension.json"
    )

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/ALBUM-UUID")

    assert browse.domain == DOMAIN
    assert browse.identifier == "ALBUM-UUID"
    assert browse.title == "ALBUM"

    assert browse.children == []


async def test_browse_unsupported(
    hass: HomeAssistant,
    mock_client: MagicMock,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
) -> None:
    """Test browsing an unsupported item."""

    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("unsupported-item.json")

    assert await async_setup_component(hass, MEDIA_SOURCE_DOMAIN, {})
    with pytest.raises(BrowseError):
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/UNSUPPORTED-ITEM-UUID")
