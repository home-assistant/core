"""Tests for the Android TV Remote remote platform."""

from unittest.mock import MagicMock, call

from androidtvremote2 import ConnectionClosed
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

MEDIA_PLAYER_ENTITY = "media_player.my_android_tv"


async def test_media_player_receives_push_updates(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test the Android TV Remote media player receives push updates and state is updated."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_api._on_is_on_updated(False)
    assert hass.states.is_state(MEDIA_PLAYER_ENTITY, STATE_OFF)

    mock_api._on_is_on_updated(True)
    assert hass.states.is_state(MEDIA_PLAYER_ENTITY, STATE_ON)

    mock_api._on_current_app_updated("com.google.android.tvlauncher")
    assert (
        hass.states.get(MEDIA_PLAYER_ENTITY).attributes.get("app_id")
        == "com.google.android.tvlauncher"
    )
    assert (
        hass.states.get(MEDIA_PLAYER_ENTITY).attributes.get("app_name")
        == "com.google.android.tvlauncher"
    )

    mock_api._on_volume_info_updated({"level": 35, "muted": False, "max": 100})
    assert hass.states.get(MEDIA_PLAYER_ENTITY).attributes.get("volume_level") == 0.35

    mock_api._on_volume_info_updated({"level": 50, "muted": True, "max": 100})
    assert hass.states.get(MEDIA_PLAYER_ENTITY).attributes.get("volume_level") == 0.50
    assert hass.states.get(MEDIA_PLAYER_ENTITY).attributes.get("is_volume_muted")

    mock_api._on_volume_info_updated({"level": 0, "muted": False, "max": 0})
    assert hass.states.get(MEDIA_PLAYER_ENTITY).attributes.get("volume_level") is None
    assert (
        hass.states.get(MEDIA_PLAYER_ENTITY).attributes.get("is_volume_muted") is None
    )

    mock_api._on_is_available_updated(False)
    assert hass.states.is_state(MEDIA_PLAYER_ENTITY, STATE_UNAVAILABLE)

    mock_api._on_is_available_updated(True)
    assert hass.states.is_state(MEDIA_PLAYER_ENTITY, STATE_ON)


async def test_media_player_toggles(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test the Android TV Remote media player toggles."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        "media_player",
        "turn_off",
        {"entity_id": MEDIA_PLAYER_ENTITY},
        blocking=True,
    )
    mock_api._on_is_on_updated(False)

    mock_api.send_key_command.assert_called_with("POWER", "SHORT")

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": MEDIA_PLAYER_ENTITY},
        blocking=True,
    )
    mock_api._on_is_on_updated(True)

    mock_api.send_key_command.assert_called_with("POWER", "SHORT")


async def test_media_player_volume(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test the Android TV Remote media player up/down/mute volume."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        "media_player",
        "volume_up",
        {"entity_id": MEDIA_PLAYER_ENTITY},
        blocking=True,
    )
    mock_api._on_volume_info_updated({"level": 10, "muted": False, "max": 100})

    mock_api.send_key_command.assert_called_with("VOLUME_UP", "SHORT")

    await hass.services.async_call(
        "media_player",
        "volume_down",
        {"entity_id": MEDIA_PLAYER_ENTITY},
        blocking=True,
    )
    mock_api._on_volume_info_updated({"level": 9, "muted": False, "max": 100})

    mock_api.send_key_command.assert_called_with("VOLUME_DOWN", "SHORT")

    await hass.services.async_call(
        "media_player",
        "volume_mute",
        {"entity_id": MEDIA_PLAYER_ENTITY, "is_volume_muted": True},
        blocking=True,
    )
    mock_api._on_volume_info_updated({"level": 9, "muted": True, "max": 100})

    mock_api.send_key_command.assert_called_with("VOLUME_MUTE", "SHORT")

    await hass.services.async_call(
        "media_player",
        "volume_mute",
        {"entity_id": MEDIA_PLAYER_ENTITY, "is_volume_muted": False},
        blocking=True,
    )
    mock_api._on_volume_info_updated({"level": 9, "muted": False, "max": 100})

    mock_api.send_key_command.assert_called_with("VOLUME_MUTE", "SHORT")


async def test_media_player_controls(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test the Android TV Remote media player play/pause/stop/next/prev."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        "media_player",
        "media_play",
        {"entity_id": MEDIA_PLAYER_ENTITY},
        blocking=True,
    )

    mock_api.send_key_command.assert_called_with("MEDIA_PLAY", "SHORT")

    await hass.services.async_call(
        "media_player",
        "media_pause",
        {"entity_id": MEDIA_PLAYER_ENTITY},
        blocking=True,
    )

    mock_api.send_key_command.assert_called_with("MEDIA_PAUSE", "SHORT")

    await hass.services.async_call(
        "media_player",
        "media_play_pause",
        {"entity_id": MEDIA_PLAYER_ENTITY},
        blocking=True,
    )

    mock_api.send_key_command.assert_called_with("MEDIA_PLAY_PAUSE", "SHORT")

    await hass.services.async_call(
        "media_player",
        "media_stop",
        {"entity_id": MEDIA_PLAYER_ENTITY},
        blocking=True,
    )

    mock_api.send_key_command.assert_called_with("MEDIA_STOP", "SHORT")

    await hass.services.async_call(
        "media_player",
        "media_previous_track",
        {"entity_id": MEDIA_PLAYER_ENTITY},
        blocking=True,
    )

    mock_api.send_key_command.assert_called_with("MEDIA_PREVIOUS", "SHORT")

    await hass.services.async_call(
        "media_player",
        "media_next_track",
        {"entity_id": MEDIA_PLAYER_ENTITY},
        blocking=True,
    )

    mock_api.send_key_command.assert_called_with("MEDIA_NEXT", "SHORT")


async def test_media_player_play_media(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test the Android TV Remote media player play_media."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": MEDIA_PLAYER_ENTITY,
            "media_content_type": "channel",
            "media_content_id": "45",
        },
        blocking=True,
    )
    assert mock_api.send_key_command.mock_calls == [
        call("4"),
        call("5"),
    ]

    # Test that set channel task has been canceled
    mock_api.send_key_command.reset_mock()
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": MEDIA_PLAYER_ENTITY,
            "media_content_type": "channel",
            "media_content_id": "7777",
        },
        blocking=False,
    )

    # Give background task time to run
    await hass.async_block_till_done()

    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": MEDIA_PLAYER_ENTITY,
            "media_content_type": "channel",
            "media_content_id": "11",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # 4 7s should be sent
    # 2 1s should be sent
    assert mock_api.send_key_command.call_count == 6

    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": MEDIA_PLAYER_ENTITY,
            "media_content_type": "url",
            "media_content_id": "https://www.youtube.com",
        },
        blocking=True,
    )
    mock_api.send_launch_app_command.assert_called_with("https://www.youtube.com")

    with pytest.raises(ValueError):
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": MEDIA_PLAYER_ENTITY,
                "media_content_type": "channel",
                "media_content_id": "abc",
            },
            blocking=True,
        )

    with pytest.raises(ValueError):
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": MEDIA_PLAYER_ENTITY,
                "media_content_type": "music",
                "media_content_id": "invalid",
            },
            blocking=True,
        )


async def test_media_player_connection_closed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test media_player raise HomeAssistantError if ConnectionClosed."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_api.send_key_command.side_effect = ConnectionClosed()
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "media_player",
            "media_pause",
            {"entity_id": MEDIA_PLAYER_ENTITY},
            blocking=True,
        )

    mock_api.send_launch_app_command.side_effect = ConnectionClosed()
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": MEDIA_PLAYER_ENTITY,
                "media_content_type": "channel",
                "media_content_id": "1",
            },
            blocking=True,
        )
