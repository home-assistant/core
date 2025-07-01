"""Test Music Assistant button entities."""

from unittest.mock import MagicMock, call

from music_assistant_models.enums import EventType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import (
    setup_integration_from_fixtures,
    snapshot_music_assistant_entities,
    trigger_subscription_callback,
)


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

    # test again without current_media
    mass_player_id = "00:00:00:00:00:02"
    music_assistant_client.players._players[mass_player_id].current_media = None
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PLAYER_CONFIG_UPDATED, mass_player_id
    )
    with pytest.raises(HomeAssistantError, match="No current item to add to favorites"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    # test again without active source
    mass_player_id = "00:00:00:00:00:02"
    music_assistant_client.players._players[mass_player_id].active_source = None
    await trigger_subscription_callback(
        hass, music_assistant_client, EventType.PLAYER_CONFIG_UPDATED, mass_player_id
    )
    with pytest.raises(HomeAssistantError, match="No current item to add to favorites"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )
