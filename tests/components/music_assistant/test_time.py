"""Test Music Assistant time entities."""

from datetime import UTC, datetime, time
from unittest.mock import AsyncMock, MagicMock

from music_assistant_models.enums import EventType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TIME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .common import (
    setup_integration_from_fixtures,
    snapshot_music_assistant_entities,
    trigger_subscription_callback,
)

MASS_PLAYER_ID = "00:00:00:00:00:01"
ENTITY_ID = "time.test_player_1_sleep_timer"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_time_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    music_assistant_client: MagicMock,
) -> None:
    """Test time entities."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    snapshot_music_assistant_entities(hass, entity_registry, snapshot, Platform.TIME)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_value_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test setting the sleep timer expiry time."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == "unknown"

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TIME: time(23, 59),
        },
        blocking=True,
    )

    assert music_assistant_client.send_command.call_count == 1
    command, kwargs = music_assistant_client.send_command.call_args
    assert command == ("players/sleep_timer/set",)
    assert kwargs["player_id"] == MASS_PLAYER_ID
    assert kwargs["seconds"] > 0


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_external_update(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test external sleep timer update."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    assert hass.states.get(ENTITY_ID).state == "unknown"

    expiry = datetime(2025, 1, 1, 22, 30, tzinfo=UTC)
    music_assistant_client.players.get_sleep_timer = AsyncMock(return_value=expiry)

    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.PLAYER_SLEEP_TIMER_UPDATED,
        MASS_PLAYER_ID,
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == dt_util.as_local(expiry).time().isoformat()
