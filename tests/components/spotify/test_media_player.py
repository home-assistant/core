"""Tests for the Spotify media player platform."""

from unittest.mock import MagicMock, patch

import pytest
from spotipy import SpotifyException
from syrupy import SnapshotAssertion

from homeassistant.components.media_player import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.components.spotify import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, load_json_value_fixture, snapshot_platform


@pytest.mark.freeze_time("2023-10-21")
@pytest.mark.usefixtures("setup_credentials")
async def test_entities(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Spotify entities."""
    with patch("secrets.token_hex", return_value="mock-token"):
        await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.freeze_time("2023-10-21")
@pytest.mark.usefixtures("setup_credentials")
async def test_podcast(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Spotify entities while listening a podcast."""
    mock_spotify.return_value.current_playback.return_value = load_json_value_fixture(
        "playback_episode.json", DOMAIN
    )
    with patch("secrets.token_hex", return_value="mock-token"):
        await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.usefixtures("setup_credentials")
async def test_free_account(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify entities with a free account."""
    mock_spotify.return_value.me.return_value["product"] = "free"
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert state.attributes["supported_features"] == 0


@pytest.mark.usefixtures("setup_credentials")
async def test_restricted_device(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify entities with a restricted device."""
    mock_spotify.return_value.current_playback.return_value["device"][
        "is_restricted"
    ] = True
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert (
        state.attributes["supported_features"] == MediaPlayerEntityFeature.SELECT_SOURCE
    )


@pytest.mark.usefixtures("setup_credentials")
async def test_spotify_dj_list(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify entities with a Spotify DJ playlist."""
    mock_spotify.return_value.current_playback.return_value["context"]["uri"] = (
        "spotify:playlist:37i9dQZF1EYkqdzj48dyYq"
    )
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert state.attributes["media_playlist"] == "DJ"


@pytest.mark.usefixtures("setup_credentials")
async def test_fetching_playlist_does_not_fail(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test failing fetching playlist does not fail update."""
    mock_spotify.return_value.playlist.side_effect = SpotifyException(
        404, "Not Found", "msg"
    )
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert "media_playlist" not in state.attributes


@pytest.mark.usefixtures("setup_credentials")
async def test_idle(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify entities in idle state."""
    mock_spotify.return_value.current_playback.return_value = {}
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert state.state == MediaPlayerState.IDLE
    assert (
        state.attributes["supported_features"] == MediaPlayerEntityFeature.SELECT_SOURCE
    )
