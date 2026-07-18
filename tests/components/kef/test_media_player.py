"""Tests for the KEF media player."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.kef.coordinator import KefCoordinator, KefData
from homeassistant.components.kef.media_player import KefConnectMediaPlayer
from homeassistant.components.media_player import MediaPlayerState
from homeassistant.core import HomeAssistant

from .conftest import FakeKefConnector

from tests.common import MockConfigEntry


def create_entity(
    hass: HomeAssistant,
    mock_connector: FakeKefConnector,
    mock_config_entry: MockConfigEntry,
    data: KefData,
) -> tuple[KefConnectMediaPlayer, KefCoordinator]:
    """Create a KEF media player with coordinator data."""
    coordinator = KefCoordinator(hass, mock_config_entry, mock_connector)
    coordinator.async_set_updated_data(data)
    coordinator.async_request_refresh = AsyncMock()
    return KefConnectMediaPlayer(coordinator, mock_config_entry), coordinator


@pytest.mark.parametrize(
    ("is_on", "is_playing", "expected_state"),
    [
        (False, False, MediaPlayerState.OFF),
        (True, False, MediaPlayerState.ON),
        (True, True, MediaPlayerState.PLAYING),
    ],
)
def test_states(
    hass: HomeAssistant,
    mock_connector: FakeKefConnector,
    mock_config_entry: MockConfigEntry,
    is_on: bool,
    is_playing: bool,
    expected_state: MediaPlayerState,
) -> None:
    """Test media player states."""
    entity, _ = create_entity(
        hass,
        mock_connector,
        mock_config_entry,
        KefData(
            is_on=is_on,
            source="wifi",
            volume=50,
            is_playing=is_playing,
            is_muted=False,
        ),
    )

    assert entity.state is expected_state


def test_volume_source_and_media(
    hass: HomeAssistant,
    mock_connector: FakeKefConnector,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test volume, source, and media properties."""
    entity, _ = create_entity(
        hass,
        mock_connector,
        mock_config_entry,
        KefData(
            is_on=True,
            source="wifi",
            volume=50,
            is_playing=True,
            is_muted=False,
            media_title="Song",
            media_artist="Artist",
            media_album="Album",
            media_image_url="https://example.com/cover.jpg",
        ),
    )

    assert entity.volume_level == 0.5
    assert not entity.is_volume_muted
    assert entity.source == "Wifi"
    assert entity.source_list == ["Wifi", "Bluetooth", "TV", "Optical"]
    assert entity.media_title == "Song"
    assert entity.media_artist == "Artist"
    assert entity.media_album_name == "Album"
    assert entity.media_image_url == "https://example.com/cover.jpg"


async def test_controls(
    hass: HomeAssistant,
    mock_connector: FakeKefConnector,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test media player controls."""
    entity, coordinator = create_entity(
        hass,
        mock_connector,
        mock_config_entry,
        KefData(
            is_on=True,
            source="wifi",
            volume=50,
            is_playing=False,
            is_muted=False,
        ),
    )

    await entity.async_turn_on()
    await entity.async_turn_off()
    await entity.async_set_volume_level(0.42)
    await entity.async_mute_volume(True)
    await entity.async_mute_volume(False)
    await entity.async_select_source("TV")
    await entity.async_media_play()
    await entity.async_media_pause()
    await entity.async_media_next_track()
    await entity.async_media_previous_track()

    mock_connector.power_on.assert_awaited_once_with()
    mock_connector.shutdown.assert_awaited_once_with()
    mock_connector.set_volume.assert_awaited_once_with(42)
    mock_connector.mute.assert_awaited_once_with()
    mock_connector.unmute.assert_awaited_once_with()
    mock_connector.set_source.assert_awaited_once_with("tv")
    assert mock_connector.toggle_play_pause.await_count == 2
    mock_connector.next_track.assert_awaited_once_with()
    mock_connector.previous_track.assert_awaited_once_with()
    assert coordinator.async_request_refresh.await_count == 10
