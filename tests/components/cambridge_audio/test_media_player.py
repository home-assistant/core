"""Tests for the Cambridge Audio integration."""

from unittest.mock import AsyncMock

from aiostreammagic import TransportControl
import pytest

from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
    MediaPlayerEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STANDBY,
)
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import ENTITY_ID

from tests.common import MockConfigEntry


async def mock_state_update(client: AsyncMock) -> None:
    """Trigger a callback in the media player."""
    await client.register_state_update_callbacks.call_args[0][0](client)


async def test_entity_supported_features(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entity attributes."""
    await setup_integration(hass, mock_config_entry)
    await mock_state_update(mock_stream_magic_client)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    attrs = state.attributes

    # Ensure volume isn't available when pre-amp is disabled
    assert not mock_stream_magic_client.state.pre_amp_mode
    assert (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        not in attrs[ATTR_SUPPORTED_FEATURES]
    )

    # Check for basic media controls
    assert {
        TransportControl.PLAY_PAUSE,
        TransportControl.TRACK_NEXT,
        TransportControl.TRACK_PREVIOUS,
    }.issubset(mock_stream_magic_client.now_playing.controls)
    assert (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        in attrs[ATTR_SUPPORTED_FEATURES]
    )
    assert (
        MediaPlayerEntityFeature.SHUFFLE_SET
        | MediaPlayerEntityFeature.REPEAT_SET
        | MediaPlayerEntityFeature.SEEK
        not in attrs[ATTR_SUPPORTED_FEATURES]
    )

    mock_stream_magic_client.now_playing.controls = [
        TransportControl.TOGGLE_REPEAT,
        TransportControl.TOGGLE_SHUFFLE,
        TransportControl.SEEK,
    ]
    await mock_state_update(mock_stream_magic_client)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    attrs = state.attributes

    assert (
        MediaPlayerEntityFeature.SHUFFLE_SET
        | MediaPlayerEntityFeature.REPEAT_SET
        | MediaPlayerEntityFeature.SEEK
        in attrs[ATTR_SUPPORTED_FEATURES]
    )

    mock_stream_magic_client.state.pre_amp_mode = True
    await mock_state_update(mock_stream_magic_client)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    attrs = state.attributes
    assert (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        in attrs[ATTR_SUPPORTED_FEATURES]
    )


@pytest.mark.parametrize(
    ("power_state", "play_state", "media_player_state"),
    [
        (True, "NETWORK", STATE_STANDBY),
        (False, "NETWORK", STATE_STANDBY),
        (False, "play", STATE_OFF),
        (True, "play", STATE_PLAYING),
        (True, "pause", STATE_PAUSED),
        (True, "connecting", STATE_BUFFERING),
        (True, "stop", STATE_IDLE),
        (True, "ready", STATE_IDLE),
    ],
)
async def test_entity_state(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    power_state: bool,
    play_state: str,
    media_player_state: str,
) -> None:
    """Test media player state."""
    await setup_integration(hass, mock_config_entry)
    mock_stream_magic_client.state.power = power_state
    mock_stream_magic_client.play_state.state = play_state
    await mock_state_update(mock_stream_magic_client)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == media_player_state


async def test_media_play_pause_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stream_magic_client: AsyncMock,
) -> None:
    """Test media next previous track service."""
    await setup_integration(hass, mock_config_entry)

    data = {ATTR_ENTITY_ID: ENTITY_ID}

    # Test for play/pause command when separate play and pause controls are unavailable
    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PAUSE, data, True)
    mock_stream_magic_client.play_pause.assert_called_once()

    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PLAY, data, True)
    assert mock_stream_magic_client.play_pause.call_count == 2

    # Test for separate play and pause controls
    mock_stream_magic_client.now_playing.controls = [
        TransportControl.PLAY,
        TransportControl.PAUSE,
    ]
    await mock_state_update(mock_stream_magic_client)
    await hass.async_block_till_done()

    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PAUSE, data, True)
    mock_stream_magic_client.pause.assert_called_once()

    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PLAY, data, True)
    mock_stream_magic_client.play.assert_called_once()


async def test_media_next_previous_track(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stream_magic_client: AsyncMock,
) -> None:
    """Test media next previous track service."""
    await setup_integration(hass, mock_config_entry)

    data = {ATTR_ENTITY_ID: ENTITY_ID}

    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_NEXT_TRACK, data, True)

    mock_stream_magic_client.next_track.assert_called_once()

    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK, data, True)

    mock_stream_magic_client.previous_track.assert_called_once()
