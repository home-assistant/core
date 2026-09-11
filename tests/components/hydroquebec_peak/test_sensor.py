"""Tests for the Hydro-Québec Peak Events sensors."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import automation
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
    snapshot_platform,
)


@pytest.mark.parametrize(
    "now",
    [
        # 12:00 EST: morning event over, evening event (16:00-20:00 EST) upcoming
        "2026-01-09T17:00:00+00:00",
        # 17:00 EST: the evening event is in progress
        "2026-01-09T22:00:00+00:00",
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    now: str,
) -> None:
    """Test the sensor entities before and during an event."""
    freezer.move_to(now)
    with patch(
        "homeassistant.components.hydroquebec_peak.PLATFORMS", [Platform.SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensors_roll_over_at_boundary(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Sensors roll to the next event shortly after the boundary, not the next poll."""
    # 19:59 EST, one minute before the 16:00-20:00 EST event ends
    freezer.move_to("2026-01-10T00:59:00+00:00")
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.cpc_d_peak_event_begins")
    assert state is not None
    assert state.state == "2026-01-09T21:00:00+00:00"

    # At the exact event end the sensors still show the finished event, so
    # time triggers scheduled on their timestamps fire before they roll over
    freezer.move_to("2026-01-10T01:00:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.cpc_d_peak_event_begins")
    assert state is not None
    assert state.state == "2026-01-09T21:00:00+00:00"

    # Shortly after the event end, the coordinator's boundary timer must fire
    freezer.move_to("2026-01-10T01:00:02+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.cpc_d_peak_event_begins")
    assert state is not None
    assert state.state == "2026-01-10T11:00:00+00:00"


async def test_time_trigger_fires_at_event_end(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A time trigger on the event end sensor fires before the sensor rolls over."""
    # 19:59 EST, one minute before the 16:00-20:00 EST event ends
    freezer.move_to("2026-01-10T00:59:00+00:00")
    await setup_integration(hass, mock_config_entry)

    calls = async_mock_service(hass, "test", "automation")
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {"trigger": "time", "at": "sensor.cpc_d_peak_event_ends"},
                "actions": {"action": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    freezer.move_to("2026-01-10T01:00:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Rolling over to the next event must not fire the trigger again
    freezer.move_to("2026-01-10T01:00:02+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_sensors_no_events(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Sensors are unknown when no event is scheduled."""
    freezer.move_to("2026-01-09T17:00:00+00:00")
    mock_client.get_events.return_value = ()
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.cpc_d_peak_event_begins")
    assert state is not None
    assert state.state == STATE_UNKNOWN
