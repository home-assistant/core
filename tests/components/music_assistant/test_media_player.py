"""Test Music Assistant media player entities."""

from unittest.mock import MagicMock, call

from syrupy import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_CLEAR_PLAYLIST,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_integration_from_fixtures, snapshot_music_assistant_entities


async def test_media_player(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    music_assistant_client: MagicMock,
) -> None:
    """Test media player."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    snapshot_music_assistant_entities(
        hass, entity_registry, snapshot, Platform.MEDIA_PLAYER
    )


async def test_media_player_basic_actions(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity basic actions (play/stop/pause etc.)."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    for action, cmd in (
        (SERVICE_MEDIA_PLAY, "play"),
        (SERVICE_MEDIA_PAUSE, "pause"),
        (SERVICE_MEDIA_STOP, "stop"),
        (SERVICE_MEDIA_PREVIOUS_TRACK, "previous"),
        (SERVICE_MEDIA_NEXT_TRACK, "next"),
        (SERVICE_VOLUME_UP, "volume_up"),
        (SERVICE_VOLUME_DOWN, "volume_down"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            action,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

        assert music_assistant_client.send_command.call_count == 1
        assert music_assistant_client.send_command.call_args == call(
            f"players/cmd/{cmd}", player_id=mass_player_id
        )
        music_assistant_client.send_command.reset_mock()


async def test_media_player_seek_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity seek action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        "media_seek",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_SEEK_POSITION: 100,
        },
        blocking=True,
    )

    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/seek", player_id=mass_player_id, position=100
    )


async def test_media_player_volume_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity volume action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_VOLUME_LEVEL: 0.5,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/volume_set", player_id=mass_player_id, volume_level=50
    )


async def test_media_player_volume_mute_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity volume_mute action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_VOLUME_MUTED: True,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/volume_mute", player_id=mass_player_id, muted=True
    )


async def test_media_player_turn_on_off_actions(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity turn_on/turn_off actions."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    for action, pwr in (
        (SERVICE_TURN_ON, True),
        (SERVICE_TURN_OFF, False),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            action,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )
        assert music_assistant_client.send_command.call_count == 1
        assert music_assistant_client.send_command.call_args == call(
            "players/cmd/power", player_id=mass_player_id, powered=pwr
        )
        music_assistant_client.send_command.reset_mock()


async def test_media_player_shuffle_set_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity shuffle_set action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SHUFFLE_SET,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_SHUFFLE: True,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/shuffle", queue_id=mass_player_id, shuffle_enabled=True
    )


async def test_media_player_repeat_set_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity repeat_set action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_REPEAT_SET,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_REPEAT: "one",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/repeat", queue_id=mass_player_id, repeat_mode="one"
    )


async def test_media_player_clear_playlist_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity clear_playlist action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_CLEAR_PLAYLIST,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/clear", queue_id=mass_player_id
    )
