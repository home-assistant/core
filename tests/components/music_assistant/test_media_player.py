"""Test Music Assistant media player entities."""

from unittest.mock import MagicMock, call

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
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


async def test_media_player_actions(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test media_player entity actions."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    mass_player_id = "00:00:00:00:00:01"
    state = hass.states.get(entity_id)
    assert state

    # test basic actions (play/stop/pause etc.)
    for action, cmd in (
        ("media_play", "play"),
        ("media_pause", "pause"),
        ("media_stop", "stop"),
        ("media_previous_track", "previous"),
        ("media_next_track", "next"),
        ("volume_up", "volume_up"),
        ("volume_down", "volume_down"),
    ):
        await hass.services.async_call(
            "media_player",
            action,
            {
                "entity_id": entity_id,
            },
            blocking=True,
        )

        assert music_assistant_client.send_command.call_count == 1
        assert music_assistant_client.send_command.call_args == call(
            f"players/cmd/{cmd}", player_id=mass_player_id
        )
        music_assistant_client.send_command.reset_mock()

    # test seek action
    await hass.services.async_call(
        "media_player",
        "media_seek",
        {
            "entity_id": entity_id,
            "seek_position": 100,
        },
        blocking=True,
    )

    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/seek", player_id=mass_player_id, position=100
    )
    music_assistant_client.send_command.reset_mock()

    # test volume action
    await hass.services.async_call(
        "media_player",
        "volume_set",
        {
            "entity_id": entity_id,
            "volume_level": 0.5,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/volume_set", player_id=mass_player_id, volume_level=50
    )
    music_assistant_client.send_command.reset_mock()

    # test volume mute action
    await hass.services.async_call(
        "media_player",
        "volume_mute",
        {
            "entity_id": entity_id,
            "is_volume_muted": True,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "players/cmd/volume_mute", player_id=mass_player_id, muted=True
    )
    music_assistant_client.send_command.reset_mock()

    # test turn_on /turn_off action
    for action, pwr in (
        ("turn_on", True),
        ("turn_off", False),
    ):
        await hass.services.async_call(
            "media_player",
            action,
            {
                "entity_id": entity_id,
            },
            blocking=True,
        )
        assert music_assistant_client.send_command.call_count == 1
        assert music_assistant_client.send_command.call_args == call(
            "players/cmd/power", player_id=mass_player_id, powered=pwr
        )
        music_assistant_client.send_command.reset_mock()

    # test shuffle action
    await hass.services.async_call(
        "media_player",
        "shuffle_set",
        {
            "entity_id": entity_id,
            "shuffle": True,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/shuffle", queue_id=mass_player_id, shuffle_enabled=True
    )
    music_assistant_client.send_command.reset_mock()

    # test repeat action
    await hass.services.async_call(
        "media_player",
        "repeat_set",
        {
            "entity_id": entity_id,
            "repeat": "one",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/repeat", queue_id=mass_player_id, repeat_mode="one"
    )
    music_assistant_client.send_command.reset_mock()

    # test clear playlist action
    await hass.services.async_call(
        "media_player",
        "clear_playlist",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "player_queues/clear", queue_id=mass_player_id
    )
    music_assistant_client.send_command.reset_mock()
