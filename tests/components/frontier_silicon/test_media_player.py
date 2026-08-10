"""Test the Frontier Silicon media player entity."""

from unittest.mock import AsyncMock

from afsapi import FSConnectionError, FSNotImplementedError, PlayCaps
import pytest

from homeassistant.components.frontier_silicon.media_player import AFSAPIMediaPlayer
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("error", "translation_key", "message"),
    [
        (FSConnectionError("Connection failed"), "connection_error", None),
        (
            FSNotImplementedError("Command is not implemented"),
            "api_error",
            "Command is not implemented",
        ),
    ],
)
async def test_async_media_previous_track_maps_errors(
    error: Exception, translation_key: str, message: str | None
) -> None:
    """Test previous track maps API failures to Home Assistant errors."""
    fs_device = AsyncMock()
    fs_device.rewind.side_effect = error
    mock_config_entry = MockConfigEntry()
    entity = AFSAPIMediaPlayer(mock_config_entry, fs_device)

    with pytest.raises(HomeAssistantError) as exc_info:
        await entity.async_media_previous_track()

    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders["command"] == "media_previous_track"

    assert (
        message is None or message in exc_info.value.translation_placeholders["message"]
    )


async def test_async_media_caps() -> None:
    """Test AFSAPI play caps translation to MediaPlayerEntityFeatures."""
    fs_device = AsyncMock()
    fs_device.get_power.return_value = False
    fs_device.get_play_caps.return_value = (
        PlayCaps.PAUSE
        | PlayCaps.STOP
        | PlayCaps.SKIP_NEXT
        | PlayCaps.SKIP_PREVIOUS
        | PlayCaps.FAST_FORWARD
        | PlayCaps.REWIND
        | PlayCaps.SHUFFLE
        | PlayCaps.REPEAT
        | PlayCaps.SEEK
        | PlayCaps.APPLY_FEEDBACK
        | PlayCaps.SCROBBLING
        | PlayCaps.ADD_PRESET
        | PlayCaps.THUMBS_UP
        | PlayCaps.THUMBS_DOWN
        | PlayCaps.SKIP_FORWARD
        | PlayCaps.SKIP_BACKWARD
        | PlayCaps.REPEAT_ONE
    )
    mock_config_entry = MockConfigEntry()
    entity = AFSAPIMediaPlayer(mock_config_entry, fs_device)
    await entity.async_update()
    assert entity.supported_features == (
        AFSAPIMediaPlayer._BASE_SUPPORTED_FEATURES
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.REPEAT_SET
        | MediaPlayerEntityFeature.SHUFFLE_SET
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )
