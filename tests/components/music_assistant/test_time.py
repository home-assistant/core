"""Test Music Assistant time entities."""

from datetime import UTC, datetime, time
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
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


@pytest.mark.parametrize(
    ("now", "value", "expected_seconds"),
    [
        pytest.param(
            "2025-06-01 20:00:00+02:00", time(23, 59), 3 * 3600 + 59 * 60, id="today"
        ),
        pytest.param("2025-06-01 20:00:00+02:00", time(8, 0), 12 * 3600, id="tomorrow"),
        pytest.param(
            "2025-06-01 20:00:00+02:00", time(20, 0), 24 * 3600, id="now_rolls_over"
        ),
        pytest.param("2025-10-25 23:00:00+02:00", time(8, 0), 10 * 3600, id="dst_end"),
        pytest.param("2025-03-29 23:00:00+01:00", time(8, 0), 8 * 3600, id="dst_start"),
        pytest.param(
            "2025-10-26 02:15:00+01:00",
            time(2, 45),
            1800,
            id="dst_repeated_hour",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_value_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    now: str,
    value: time,
    expected_seconds: int,
) -> None:
    """Test setting the sleep timer expiry time."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(now)
    await setup_integration_from_fixtures(hass, music_assistant_client)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == "unknown"
    music_assistant_client.send_command.return_value = (
        dt_util.utcnow().timestamp() + expected_seconds
    )

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TIME: value,
        },
        blocking=True,
    )

    music_assistant_client.send_command.assert_called_once_with(
        "players/sleep_timer/set", player_id=MASS_PLAYER_ID, seconds=expected_seconds
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_external_update(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test external sleep timer update."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    assert hass.states.get(ENTITY_ID).state == "unknown"

    expiry = datetime(2025, 1, 1, 22, 30, tzinfo=UTC)
    music_assistant_client.players._players[
        MASS_PLAYER_ID
    ].sleep_timer_expires_at = expiry.timestamp()

    await trigger_subscription_callback(
        hass,
        music_assistant_client,
        EventType.PLAYER_SLEEP_TIMER_UPDATED,
        MASS_PLAYER_ID,
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == dt_util.as_local(expiry).time().isoformat()
