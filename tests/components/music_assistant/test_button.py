"""Test Music Assistant button entities."""

from unittest.mock import MagicMock, call

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_integration_from_fixtures, snapshot_music_assistant_entities


async def test_button_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    music_assistant_client: MagicMock,
) -> None:
    """Test media player."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    snapshot_music_assistant_entities(hass, entity_registry, snapshot, Platform.BUTTON)


async def test_button_press_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test button press action."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "button.my_super_test_player_2_favorite_current_song"
    state = hass.states.get(entity_id)
    assert state
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "music/favorites/add_item",
        item="spotify://track/5d95dc5be77e4f7eb4939f62cfef527b",
    )
