"""Tests for the lastfm sensor."""

from unittest.mock import AsyncMock

from pylast import WSError
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from ..analytics_insights import setup_integration

from tests.common import MockConfigEntry


async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lastfm_network: AsyncMock,
    mock_lastfm_user: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensors."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "sensor.lastfm_testaccount1"

    state = hass.states.get(entity_id)

    assert state == snapshot


async def test_first_time_user_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lastfm_network: AsyncMock,
    mock_lastfm_user: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test first time user state."""
    mock_lastfm_user.get_playcount.return_value = 0
    mock_lastfm_user.get_recent_tracks.return_value = []
    mock_lastfm_user.get_top_tracks.return_value = []
    mock_lastfm_user.get_now_playing.return_value = None
    await setup_integration(hass, mock_config_entry)

    entity_id = "sensor.lastfm_testaccount1"

    state = hass.states.get(entity_id)

    assert state == snapshot


async def test_non_existent_user(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lastfm_network: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test non existent user."""
    mock_lastfm_network.get_user.side_effect = WSError(
        "network", "status", "User not found"
    )
    await setup_integration(hass, mock_config_entry)

    entity_id = "sensor.lastfm_testaccount1"

    state = hass.states.get(entity_id)

    assert state == snapshot
