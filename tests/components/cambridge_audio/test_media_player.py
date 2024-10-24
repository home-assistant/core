"""Tests for the Cambridge Audio integration."""

from unittest.mock import AsyncMock

from aiostreammagic import (
    RepeatMode as CambridgeRepeatMode,
    ShuffleMode,
    TransportControl,
)
from aiostreammagic.models import CallbackType
import pytest

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaPlayerEntityFeature,
    RepeatMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STANDBY,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration
from .const import ENTITY_ID

from tests.common import MockConfigEntry


async def mock_state_update(client: AsyncMock) -> None:
    """Trigger a callback in the media player."""
    for callback in client.register_state_update_callbacks.call_args_list:
        await callback[0][0](client, CallbackType.STATE)


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
        (True, "other", STATE_ON),
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
        TransportControl.STOP,
    ]
    await mock_state_update(mock_stream_magic_client)
    await hass.async_block_till_done()

    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PAUSE, data, True)
    mock_stream_magic_client.pause.assert_called_once()

    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PLAY, data, True)
    mock_stream_magic_client.play.assert_called_once()

    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_STOP, data, True)
    mock_stream_magic_client.stop.assert_called_once()


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


async def test_shuffle_repeat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stream_magic_client: AsyncMock,
) -> None:
    """Test shuffle and repeat service."""
    await setup_integration(hass, mock_config_entry)

    mock_stream_magic_client.now_playing.controls = [
        TransportControl.TOGGLE_SHUFFLE,
        TransportControl.TOGGLE_REPEAT,
    ]

    # Test shuffle
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SHUFFLE_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_SHUFFLE: False},
    )

    mock_stream_magic_client.set_shuffle.assert_called_with(ShuffleMode.OFF)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SHUFFLE_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_SHUFFLE: True},
    )

    mock_stream_magic_client.set_shuffle.assert_called_with(ShuffleMode.ALL)

    # Test repeat
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_REPEAT_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_REPEAT: RepeatMode.OFF},
    )

    mock_stream_magic_client.set_repeat.assert_called_with(CambridgeRepeatMode.OFF)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_REPEAT_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_REPEAT: RepeatMode.ALL},
    )

    mock_stream_magic_client.set_repeat.assert_called_with(CambridgeRepeatMode.ALL)


async def test_power_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stream_magic_client: AsyncMock,
) -> None:
    """Test power service."""
    await setup_integration(hass, mock_config_entry)

    data = {ATTR_ENTITY_ID: ENTITY_ID}

    await hass.services.async_call(MP_DOMAIN, SERVICE_TURN_ON, data, True)

    mock_stream_magic_client.power_on.assert_called_once()

    await hass.services.async_call(MP_DOMAIN, SERVICE_TURN_OFF, data, True)

    mock_stream_magic_client.power_off.assert_called_once()


async def test_media_seek(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stream_magic_client: AsyncMock,
) -> None:
    """Test media seek service."""
    await setup_integration(hass, mock_config_entry)

    mock_stream_magic_client.now_playing.controls = [
        TransportControl.SEEK,
    ]

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_MEDIA_SEEK,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_SEEK_POSITION: 100},
    )

    mock_stream_magic_client.media_seek.assert_called_once_with(100)


async def test_play_media_preset_item_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stream_magic_client: AsyncMock,
) -> None:
    """Test playing media with a preset item id."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: "preset",
            ATTR_MEDIA_CONTENT_ID: "1",
        },
        blocking=True,
    )
    assert mock_stream_magic_client.recall_preset.call_count == 1
    assert mock_stream_magic_client.recall_preset.call_args_list[0].args[0] == 1

    with pytest.raises(ServiceValidationError, match="Missing preset for media_id: 10"):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: "preset",
                ATTR_MEDIA_CONTENT_ID: "10",
            },
            blocking=True,
        )

    with pytest.raises(
        ServiceValidationError, match="Preset must be an integer, got: UNKNOWN_PRESET"
    ):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: "preset",
                ATTR_MEDIA_CONTENT_ID: "UNKNOWN_PRESET",
            },
            blocking=True,
        )


async def test_play_media_airable_radio_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stream_magic_client: AsyncMock,
) -> None:
    """Test playing media with an airable radio id."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: "airable",
            ATTR_MEDIA_CONTENT_ID: "12345678",
        },
        blocking=True,
    )
    assert mock_stream_magic_client.play_radio_airable.call_count == 1
    call_args = mock_stream_magic_client.play_radio_airable.call_args_list[0].args
    assert call_args[0] == "Radio"
    assert call_args[1] == 12345678


async def test_play_media_internet_radio(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stream_magic_client: AsyncMock,
) -> None:
    """Test playing media with a url."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: "internet_radio",
            ATTR_MEDIA_CONTENT_ID: "https://example.com",
        },
        blocking=True,
    )
    assert mock_stream_magic_client.play_radio_url.call_count == 1
    call_args = mock_stream_magic_client.play_radio_url.call_args_list[0].args
    assert call_args[0] == "Radio"
    assert call_args[1] == "https://example.com"


async def test_play_media_unknown_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stream_magic_client: AsyncMock,
) -> None:
    """Test playing media with an unsupported content type."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        HomeAssistantError,
        match="Unsupported media type for Cambridge Audio device: unsupported_content_type",
    ):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: "unsupported_content_type",
                ATTR_MEDIA_CONTENT_ID: "1",
            },
            blocking=True,
        )
