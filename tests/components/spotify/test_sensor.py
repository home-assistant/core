"""Tests for the Spotify sensor platform."""

from unittest.mock import MagicMock, patch

import pytest
from spotifyaio import PlaybackState
from syrupy import SnapshotAssertion

from homeassistant.components.spotify import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, load_fixture, snapshot_platform


@pytest.mark.usefixtures("setup_credentials")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Spotify entities."""
    with patch("homeassistant.components.spotify.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("setup_credentials")
async def test_audio_features_unavailable(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Spotify entities."""
    mock_spotify.return_value.get_audio_features.return_value = None

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.spotify_spotify_1_song_tempo").state == STATE_UNKNOWN


@pytest.mark.usefixtures("setup_credentials")
async def test_audio_features_unknown_during_podcast(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Spotify audio features sensor during a podcast."""
    mock_spotify.return_value.get_playback.return_value = PlaybackState.from_json(
        load_fixture("playback_episode.json", DOMAIN)
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.spotify_spotify_1_song_tempo").state == STATE_UNKNOWN
