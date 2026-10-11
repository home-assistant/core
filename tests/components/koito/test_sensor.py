"""Test all registered sensor states and metadata."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiokoito import (
    KoitoAuthenticationError,
    KoitoConnectionError,
    MusicItem,
    NowPlaying,
    RankedItem,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.parametrize("platform", [Platform.SENSOR, Platform.BINARY_SENSOR])
async def test_entities(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    platform: Platform,
) -> None:
    """Snapshot every entity's state and registry metadata."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.koito.PLATFORMS", [platform]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_recovery_and_reauth(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Recover after an outage and start reauth after authentication fails."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval.total_seconds() == 60
    mock_client.async_fetch_data.side_effect = KoitoConnectionError()
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.koito_plays").state == "unavailable"
    mock_client.async_fetch_data.side_effect = None
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.koito_plays").state == "42"
    mock_client.async_fetch_data.side_effect = KoitoAuthenticationError()
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.config_entries.flow.async_progress()[0]["context"]["source"] == "reauth"


async def test_healthy_unload_stops_polling(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unload a healthy entry without leaving background API requests running."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.async_fetch_data.reset_mock()
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_client.async_fetch_data.assert_awaited_once()
    assert hass.states.get("sensor.koito_plays").state == "42"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.async_fetch_data.reset_mock()
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_client.async_fetch_data.assert_not_awaited()


async def test_server_backoff(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Preserve the server delay when scheduling the next coordinated refresh."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data
    mock_client.async_fetch_data.side_effect = KoitoConnectionError(
        "backoff", status=429, retry_after=120
    )
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.last_exception.retry_after == 120
    mock_client.async_fetch_data.reset_mock()
    mock_client.async_fetch_data.side_effect = None
    # Allow for Core's second rounding and the time helper's 0.5-second offset.
    freezer.tick(timedelta(seconds=118))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_client.async_fetch_data.await_count == 0
    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_client.async_fetch_data.await_count == 1
    assert hass.states.get("sensor.koito_plays").state == "42"
    mock_client.async_fetch_data.assert_awaited_with(period="all_time")


async def test_optional_playback_unavailable(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A lost optional endpoint clears track details without losing statistics."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.async_fetch_data.return_value = replace(
        mock_client.async_fetch_data.return_value, now_playing=None
    )
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.koito_plays").state == "42"
    assert hass.states.get("binary_sensor.koito_now_playing").state == "unavailable"
    track = hass.states.get("sensor.koito_currently_playing_track")
    assert track.state == "unknown"
    assert "title" not in track.attributes
    assert "image_url" not in track.attributes


@pytest.mark.parametrize("active", [False, True])
async def test_sparse_playback(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    active: bool,
) -> None:
    """Inactive playback clears stale details; sparse active details stay valid."""
    mock_client.async_fetch_data.return_value = replace(
        mock_client.async_fetch_data.return_value,
        now_playing=NowPlaying(currently_playing=active, track=MusicItem(album_id=9)),
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    playback = hass.states.get("binary_sensor.koito_now_playing")
    assert playback.state == ("on" if active else "off")
    assert playback.attributes.get("album_id") == (9 if active else None)
    assert "title" not in playback.attributes
    assert "image_url" not in playback.attributes
    assert hass.states.get("sensor.koito_currently_playing_track").state == "unknown"


async def test_empty_rankings(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Empty rankings expose unknown states rather than stale previous leaders."""
    data = mock_client.async_fetch_data.return_value
    mock_client.async_fetch_data.return_value = replace(
        data,
        summary=replace(data.summary, top_artists=(), top_albums=(), top_tracks=()),
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.koito_plays").state == "42"
    for name in ("artist", "album", "track"):
        state = hass.states.get(f"sensor.koito_top_{name}")
        assert state.state == "unknown"
        assert "title" not in state.attributes


async def test_empty_music_labels(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A valid ranked item without display text remains unknown."""
    data = mock_client.async_fetch_data.return_value
    mock_client.async_fetch_data.return_value = replace(
        data,
        summary=replace(
            data.summary,
            top_artists=(RankedItem(rank=1, item=MusicItem(name="  ")),),
        ),
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.koito_top_artist").state == "unknown"
