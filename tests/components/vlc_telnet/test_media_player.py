"""Test the VLC media player Telnet integration."""

from datetime import timedelta
from unittest.mock import MagicMock, call

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
    ("repeat", "expected_calls"),
    [
        pytest.param(RepeatMode.OFF, [call.loop("off"), call.repeat("off")], id="off"),
        pytest.param(RepeatMode.ONE, [call.repeat("on")], id="one"),
        pytest.param(RepeatMode.ALL, [call.loop("on"), call.repeat("off")], id="all"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_repeat_set(
    hass: HomeAssistant,
    vlc_mock: MagicMock,
    repeat: RepeatMode,
    expected_calls: list,
) -> None:
    """Test that repeat_set sends the VLC loop and repeat commands in order."""
    vlc_mock.reset_mock()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_REPEAT_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_REPEAT: repeat},
        blocking=True,
    )

    assert [
        method_call
        for method_call in vlc_mock.method_calls
        if method_call[0] in ("loop", "repeat")
    ] == expected_calls
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_MEDIA_REPEAT] == repeat


@pytest.mark.parametrize(
    ("previous", "repeat", "failing_method", "expected"),
    [
        pytest.param(
            RepeatMode.ONE, RepeatMode.ALL, "loop", RepeatMode.ONE, id="one_loop_fails"
        ),
        pytest.param(
            RepeatMode.ONE, RepeatMode.ALL, "repeat", None, id="one_repeat_fails"
        ),
        pytest.param(RepeatMode.OFF, RepeatMode.ALL, "loop", None, id="off_loop_fails"),
        pytest.param(
            RepeatMode.ALL, RepeatMode.ONE, "repeat", None, id="all_repeat_fails"
        ),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_repeat_set_failure_keeps_confirmed_mode(
    hass: HomeAssistant,
    vlc_mock: MagicMock,
    previous: RepeatMode,
    repeat: RepeatMode,
    failing_method: str,
    expected: RepeatMode | None,
) -> None:
    """Test that a failed VLC command leaves only the mode VLC has confirmed."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_REPEAT_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_REPEAT: previous},
        blocking=True,
    )
    getattr(vlc_mock, failing_method).side_effect = CommandError("test error")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_REPEAT_SET,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_REPEAT: repeat},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes.get(ATTR_MEDIA_REPEAT) == expected
