"""Tests for the Spotify switch entity."""

from unittest.mock import MagicMock, patch

import pytest
from spotifyaio import SpotifyConnectionError
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("setup_credentials")
async def test_entities(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Spotify entities."""
    with (
        patch("homeassistant.components.spotify.PLATFORMS", [Platform.SWITCH]),
    ):
        await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.usefixtures("setup_credentials")
async def test_fetching_state_doesnt_block(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test fetching the state doesn't block the update."""
    mock_spotify.are_tracks_saved.side_effect = SpotifyConnectionError("Error")

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.spotify_spotify_1_added_to_library") is not None
