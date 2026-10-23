"""Tests for the Hydro-Québec Peak Events binary sensors."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

PEAK_ACTIVE = "binary_sensor.cpc_d_peak_event_in_progress"
TODAY_PM = "binary_sensor.cpc_d_peak_event_today_pm"
TOMORROW_AM = "binary_sensor.cpc_d_peak_event_tomorrow_am"


@pytest.mark.parametrize(
    "now",
    [
        # 12:00 EST: AM and PM events today, AM event tomorrow
        "2026-01-09T17:00:00+00:00",
        # 17:00 EST: the evening event is in progress
        "2026-01-09T22:00:00+00:00",
    ],
)
async def test_binary_sensors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    now: str,
) -> None:
    """Test the binary sensor entities before and during an event."""
    freezer.move_to(now)
    with patch(
        "homeassistant.components.hydroquebec_peak.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_peak_active_flips_at_boundary(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The in-progress flag flips shortly after the event start, not the next poll."""
    # 15:59 EST, one minute before the 16:00-20:00 EST event
    freezer.move_to("2026-01-09T20:59:00+00:00")
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(PEAK_ACTIVE)
    assert state is not None
    assert state.state == STATE_OFF

    freezer.move_to("2026-01-09T21:00:02+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(PEAK_ACTIVE)
    assert state is not None
    assert state.state == STATE_ON


async def test_day_flags_roll_over_at_midnight(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Day flags roll over at local midnight, not the next poll."""
    # 23:59 EST, the night before the 2026-01-10 AM event
    freezer.move_to("2026-01-10T04:59:00+00:00")
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(TODAY_PM).state == STATE_ON
    assert hass.states.get(TOMORROW_AM).state == STATE_ON

    freezer.move_to("2026-01-10T05:00:02+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TODAY_PM).state == STATE_OFF
    assert hass.states.get(TOMORROW_AM).state == STATE_OFF
