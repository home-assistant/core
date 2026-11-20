"""Tests for the Yoto sensor platform."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

pytestmark = pytest.mark.usefixtures("setup_credentials")

ENTITY_ID = "sensor.nursery_yoto_battery"
SLEEP_TIMER_ENTITY_ID = "sensor.nursery_yoto_sleep_timer"


@pytest.mark.usefixtures("mock_yoto_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot every Yoto sensor entity."""
    with patch("homeassistant.components.yoto.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_unavailable_when_offline(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Sensors are unavailable while the player is offline."""
    player = next(iter(mock_yoto_client.players.values()))
    player.is_online = False

    with patch("homeassistant.components.yoto.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_sleep_timer_end(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The sleep timer sensor reports when the timer ends."""
    player = mock_yoto_client.players["player-test"]
    player.sleep_timer_ends_at = datetime(2026, 5, 8, 12, 30, tzinfo=UTC)

    with patch("homeassistant.components.yoto.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(SLEEP_TIMER_ENTITY_ID).state == "2026-05-08T12:30:00+00:00"

    on_update = mock_yoto_client.connect_events.call_args.args[1]

    # A small shift from the per-second countdown keeps the same end time.
    player.sleep_timer_ends_at = datetime(2026, 5, 8, 12, 30, 2, tzinfo=UTC)
    on_update(player)
    await hass.async_block_till_done()
    assert hass.states.get(SLEEP_TIMER_ENTITY_ID).state == "2026-05-08T12:30:00+00:00"

    player.sleep_timer_ends_at = datetime(2026, 5, 8, 12, 20, tzinfo=UTC)
    on_update(player)
    await hass.async_block_till_done()
    assert hass.states.get(SLEEP_TIMER_ENTITY_ID).state == "2026-05-08T12:20:00+00:00"

    player.sleep_timer_ends_at = None
    on_update(player)
    await hass.async_block_till_done()
    assert hass.states.get(SLEEP_TIMER_ENTITY_ID).state == STATE_UNKNOWN
