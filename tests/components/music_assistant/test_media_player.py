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


async def test_base_media_player_actions(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test base media_player entity actions."""
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
