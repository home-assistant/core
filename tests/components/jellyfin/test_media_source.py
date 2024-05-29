"""Tests for the Jellyfin media_player platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.jellyfin.const import DOMAIN
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


@pytest.fixture(autouse=True)
async def setup_component(hass: HomeAssistant) -> None:
    """Set up component."""
    assert await async_setup_component(hass, MEDIA_SOURCE_DOMAIN, {})


async def test_resolve(
    hass: HomeAssistant,
    mock_client: MagicMock,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test resolving Jellyfin media items."""

    # Test resolving a track
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("track.json")

    play_media = await async_resolve_media(
        hass, f"{URI_SCHEME}{DOMAIN}/TRACK-UUID", "media_player.jellyfin_device"
    )

    assert play_media.mime_type == "audio/flac"
    assert play_media.url == snapshot

    mock_api.audio_url.assert_called_with("TRACK-UUID")
    assert mock_api.audio_url.call_count == 1
    mock_api.audio_url.reset_mock()

    # Test resolving a movie
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("movie.json")

    play_media = await async_resolve_media(
        hass, f"{URI_SCHEME}{DOMAIN}/MOVIE-UUID", "media_player.jellyfin_device"
    )

    assert play_media.mime_type == "video/mp4"
    assert play_media.url == snapshot

    # Test resolving an unsupported item
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("unsupported-item.json")

    with pytest.raises(BrowseError):
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/UNSUPPORTED-ITEM-UUID",
            "media_player.jellyfin_device",
        )


@pytest.mark.parametrize(
    "audio_codec",
    [("aac"), ("wma"), ("vorbis"), ("mp3")],
)
async def test_audio_codec_resolve(
    hass: HomeAssistant,
    mock_client: MagicMock,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
    audio_codec: str,
) -> None:
    """Test resolving Jellyfin media items with audio codec."""

    # Test resolving a track
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("track.json")

    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"audio_codec": audio_codec}
    )
    assert init_integration.options["audio_codec"] == audio_codec

    play_media = await async_resolve_media(
        hass, f"{URI_SCHEME}{DOMAIN}/TRACK-UUID", "media_player.jellyfin_device"
    )

    assert play_media.mime_type == "audio/flac"
    assert play_media.url == snapshot

    mock_api.audio_url.assert_called_with("TRACK-UUID", audio_codec=audio_codec)
    assert mock_api.audio_url.call_count == 1


async def test_root(
    hass: HomeAssistant,
    mock_client: MagicMock,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test browsing the Jellyfin root."""

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")

    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == "Jellyfin"
    assert vars(browse.children[0]) == snapshot


async def test_tv_library(
    hass: HomeAssistant,
    mock_client: MagicMock,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test browsing a Jellyfin TV Library."""

    # Test browsing an empty tv library
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("tv-collection.json")
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = {"Items": []}

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
    assert vars(browse.children[0]) == snapshot

    # Test browsing a series
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("series.json")
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = load_json_fixture("seasons.json")

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/SERIES-UUID")

    assert browse.domain == DOMAIN
    assert browse.identifier == "SERIES-UUID"
    assert browse.title == "SERIES"
    assert vars(browse.children[0]) == snapshot

    # Test browsing a season
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("season.json")
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = load_json_fixture("episodes.json")

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/SEASON-UUID")

    assert browse.domain == DOMAIN
    assert browse.identifier == "SEASON-UUID"
    assert browse.title == "SEASON"
    assert vars(browse.children[0]) == snapshot


async def test_movie_library(
    hass: HomeAssistant,
    mock_client: MagicMock,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test browsing a Jellyfin Movie Library."""

    # Test empty movie library
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("movie-collection.json")
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = {"Items": []}

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
    assert vars(browse.children[0]) == snapshot


async def test_music_library(
    hass: HomeAssistant,
    mock_client: MagicMock,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test browsing a Jellyfin Music Library."""

    # Test browsinng an empty music library
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("music-collection.json")
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = {"Items": []}

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
    assert vars(browse.children[0]) == snapshot

    # Test browsing an artist
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("artist.json")
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = load_json_fixture("albums.json")

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/ARTIST-UUID")

    assert browse.domain == DOMAIN
    assert browse.identifier == "ARTIST-UUID"
    assert browse.title == "ARTIST"
    assert vars(browse.children[0]) == snapshot

    # Test browsing an album
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = load_json_fixture("album.json")
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = load_json_fixture("tracks.json")

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/ALBUM-UUID")

    assert browse.domain == DOMAIN
    assert browse.identifier == "ALBUM-UUID"
    assert browse.title == "ALBUM"
    assert vars(browse.children[0]) == snapshot

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

    with pytest.raises(BrowseError):
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/UNSUPPORTED-ITEM-UUID")
