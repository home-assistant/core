"""Test the VLC media player Telnet integration."""

from datetime import timedelta
from unittest.mock import MagicMock

from aiovlc.exceptions import CommandError, ConnectError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SCAN_INTERVAL,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_PLAY_MEDIA,
    MediaType,
    RepeatMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

ENTITY_ID = "media_player.vlc_telnet"


@pytest.mark.parametrize(
    ("service", "service_data", "vlc_method"),
    [
        pytest.param(
            SERVICE_MEDIA_SEEK,
            {ATTR_MEDIA_SEEK_POSITION: 100.0},
            "seek",
            id="media_seek",
        ),
        pytest.param(
            SERVICE_VOLUME_MUTE,
            {ATTR_MEDIA_VOLUME_MUTED: True},
            "set_volume",
            id="volume_mute",
        ),
        pytest.param(
            SERVICE_VOLUME_SET,
            {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
            "set_volume",
            id="volume_set",
        ),
        pytest.param(
            SERVICE_MEDIA_PLAY,
            {},
            "status",
            id="media_play",
        ),
        pytest.param(
            SERVICE_MEDIA_PAUSE,
            {},
            "status",
            id="media_pause",
        ),
        pytest.param(
            SERVICE_MEDIA_STOP,
            {},
            "stop",
            id="media_stop",
        ),
        pytest.param(
            SERVICE_PLAY_MEDIA,
            {
                ATTR_MEDIA_CONTENT_ID: "test.mp3",
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            },
            "add",
            id="play_media",
        ),
        pytest.param(
            SERVICE_MEDIA_PREVIOUS_TRACK,
            {},
            "prev",
            id="media_previous_track",
        ),
        pytest.param(
            SERVICE_MEDIA_NEXT_TRACK,
            {},
            "next",
            id="media_next_track",
        ),
        pytest.param(
            SERVICE_CLEAR_PLAYLIST,
            {},
            "clear",
            id="clear_playlist",
        ),
        pytest.param(
            SERVICE_SHUFFLE_SET,
            {ATTR_MEDIA_SHUFFLE: True},
            "random",
            id="shuffle_set",
        ),
        pytest.param(
            SERVICE_REPEAT_SET,
            {ATTR_MEDIA_REPEAT: RepeatMode.ONE},
            "repeat",
            id="repeat_set_repeat",
        ),
        pytest.param(
            SERVICE_REPEAT_SET,
            {ATTR_MEDIA_REPEAT: RepeatMode.ALL},
            "loop",
            id="repeat_set_loop",
        ),
    ],
)
@pytest.mark.parametrize(
    ("error_class", "translation_key"),
    [
        pytest.param(CommandError, "command_error", id="command_error"),
        pytest.param(ConnectError, "connect_error", id="connect_error"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_action_handler_raises_homeassistant_error(
    hass: HomeAssistant,
    vlc_mock: MagicMock,
    service: str,
    service_data: dict,
    vlc_method: str,
    error_class: type[Exception],
    translation_key: str,
) -> None:
    """Test that action handlers raise HomeAssistantError on VLC errors."""
    getattr(vlc_mock, vlc_method).side_effect = error_class("test error")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
            blocking=True,
        )
    assert exc_info.value.translation_key == translation_key


@pytest.mark.parametrize(
    ("error_class", "expected_state", "expected_log"),
    [
        pytest.param(
            CommandError, "idle", "Command error: test error", id="command_error"
        ),
        pytest.param(
            ConnectError,
            STATE_UNAVAILABLE,
            "Connection error: test error",
            id="connect_error",
        ),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_update_logs_error_instead_of_raising(
    hass: HomeAssistant,
    vlc_mock: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    error_class: type[Exception],
    expected_state: str,
    expected_log: str,
) -> None:
    """Test that async_update logs VLC errors instead of raising."""
    vlc_mock.status.side_effect = error_class("test error")

    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == expected_state
    assert expected_log in caplog.text


@pytest.mark.parametrize(
    ("repeat", "repeat_command", "loop_command"),
    [
        pytest.param(RepeatMode.OFF, "off", "off", id="off"),
        pytest.param(RepeatMode.ONE, "on", "off", id="one"),
        pytest.param(RepeatMode.ALL, "off", "on", id="all"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_repeat_set(
    hass: HomeAssistant,
    vlc_mock: MagicMock,
    repeat: RepeatMode,
    repeat_command: str,
    loop_command: str,
) -> None:
    """Test that repeat_set sends the VLC repeat and loop commands."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_REPEAT_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_REPEAT: repeat},
        blocking=True,
    )

    vlc_mock.repeat.assert_awaited_once_with(repeat_command)
    vlc_mock.loop.assert_awaited_once_with(loop_command)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_MEDIA_REPEAT] == repeat


@pytest.mark.parametrize(
    "error_class",
    [
        pytest.param(CommandError, id="command_error"),
        pytest.param(ConnectError, id="connect_error"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_repeat_set_partial_failure_clears_repeat(
    hass: HomeAssistant,
    vlc_mock: MagicMock,
    error_class: type[Exception],
) -> None:
    """Test that a failed loop command after a successful repeat clears the mode."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_REPEAT_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_REPEAT: RepeatMode.ONE},
        blocking=True,
    )
    vlc_mock.loop.side_effect = error_class("test error")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_REPEAT_SET,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_REPEAT: RepeatMode.ALL},
            blocking=True,
        )

    vlc_mock.repeat.assert_awaited_with("off")
    state = hass.states.get(ENTITY_ID)
    assert state
    assert ATTR_MEDIA_REPEAT not in state.attributes
