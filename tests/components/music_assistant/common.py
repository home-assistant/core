"""Provide common test tools."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from music_assistant_models.enums import EventType
from music_assistant_models.media_items import Album, Artist, Playlist, Radio, Track
from music_assistant_models.player import Player
from music_assistant_models.player_queue import PlayerQueue
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, load_json_object_fixture

MASS_DOMAIN = "music_assistant"
MOCK_URL = "http://mock-music_assistant-server-url"


def load_and_parse_fixture(fixture: str) -> dict[str, Any]:
    """Load and parse a fixture."""
    data = load_json_object_fixture(f"music_assistant/{fixture}.json")
    return data[fixture]


async def setup_integration_from_fixtures(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> MockConfigEntry:
    """Set up MusicAssistant integration with fixture data."""
    players = create_players_from_fixture()
    music_assistant_client.players._players = {x.player_id: x for x in players}
    player_queues = create_player_queues_from_fixture()
    music_assistant_client.player_queues._queues = {
        x.queue_id: x for x in player_queues
    }
    config_entry = MockConfigEntry(
        domain=MASS_DOMAIN,
        data={"url": MOCK_URL},
        unique_id=music_assistant_client.server_info.server_id,
    )
    music = music_assistant_client.music
    library_artists = create_library_artists_from_fixture()
    music.get_library_artists = AsyncMock(return_value=library_artists)
    library_artist_albums = create_library_artist_albums_from_fixture()
    music.get_artist_albums = AsyncMock(return_value=library_artist_albums)
    library_albums = create_library_albums_from_fixture()
    music.get_library_albums = AsyncMock(return_value=library_albums)
    library_album_tracks = create_library_album_tracks_from_fixture()
    music.get_album_tracks = AsyncMock(return_value=library_album_tracks)
    library_tracks = create_library_tracks_from_fixture()
    music.get_library_tracks = AsyncMock(return_value=library_tracks)
    library_playlists = create_library_playlists_from_fixture()
    music.get_library_playlists = AsyncMock(return_value=library_playlists)
    library_playlist_tracks = create_library_playlist_tracks_from_fixture()
    music.get_playlist_tracks = AsyncMock(return_value=library_playlist_tracks)
    library_radios = create_library_radios_from_fixture()
    music.get_library_radios = AsyncMock(return_value=library_radios)
    music.get_item_by_uri = AsyncMock()

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


def create_players_from_fixture() -> list[Player]:
    """Create MA Players from fixture."""
    fixture_data = load_and_parse_fixture("players")
    return [Player.from_dict(player_data) for player_data in fixture_data]


def create_player_queues_from_fixture() -> list[Player]:
    """Create MA PlayerQueues from fixture."""
    fixture_data = load_and_parse_fixture("player_queues")
    return [
        PlayerQueue.from_dict(player_queue_data) for player_queue_data in fixture_data
    ]


def create_library_albums_from_fixture() -> list[Album]:
    """Create MA Albums from fixture."""
    fixture_data = load_and_parse_fixture("library_albums")
    return [Album.from_dict(album_data) for album_data in fixture_data]


def create_library_album_tracks_from_fixture() -> list[Track]:
    """Create MA Tracks from fixture."""
    fixture_data = load_and_parse_fixture("library_album_tracks")
    return [Track.from_dict(track_data) for track_data in fixture_data]


def create_library_tracks_from_fixture() -> list[Track]:
    """Create MA Tracks from fixture."""
    fixture_data = load_and_parse_fixture("library_tracks")
    return [Track.from_dict(track_data) for track_data in fixture_data]


def create_library_artists_from_fixture() -> list[Artist]:
    """Create MA Artists from fixture."""
    fixture_data = load_and_parse_fixture("library_artists")
    return [Artist.from_dict(artist_data) for artist_data in fixture_data]


def create_library_artist_albums_from_fixture() -> list[Album]:
    """Create MA Albums from fixture."""
    fixture_data = load_and_parse_fixture("library_artist_albums")
    return [Album.from_dict(album_data) for album_data in fixture_data]


def create_library_playlists_from_fixture() -> list[Playlist]:
    """Create MA Playlists from fixture."""
    fixture_data = load_and_parse_fixture("library_playlists")
    return [Playlist.from_dict(playlist_data) for playlist_data in fixture_data]


def create_library_playlist_tracks_from_fixture() -> list[Track]:
    """Create MA Tracks from fixture."""
    fixture_data = load_and_parse_fixture("library_playlist_tracks")
    return [Track.from_dict(track_data) for track_data in fixture_data]


def create_library_radios_from_fixture() -> list[Radio]:
    """Create MA Radios from fixture."""
    fixture_data = load_and_parse_fixture("library_radios")
    return [Radio.from_dict(radio_data) for radio_data in fixture_data]


async def trigger_subscription_callback(
    hass: HomeAssistant,
    client: MagicMock,
    event: EventType = EventType.PLAYER_UPDATED,
    data: Any = None,
) -> None:
    """Trigger a subscription callback."""
    # trigger callback on all subscribers
    for sub in client.subscribe_events.call_args_list:
        callback = sub.kwargs["callback"]
        event_filter = sub.kwargs.get("event_filter")
        if event_filter in (None, event):
            callback(event, data)
    await hass.async_block_till_done()


def snapshot_music_assistant_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    platform: Platform,
) -> None:
    """Snapshot MusicAssistant entities."""
    entities = hass.states.async_all(platform)
    for entity_state in entities:
        entity_entry = entity_registry.async_get(entity_state.entity_id)
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert entity_state == snapshot(name=f"{entity_entry.entity_id}-state")
