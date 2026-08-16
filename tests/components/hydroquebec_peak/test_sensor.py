"""Tests for the Hydro-Québec Peak Events sensors."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensors_next_event(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Sensors expose the upcoming event when none is active."""
    # 12:00 EST: morning event over, evening event (16:00-20:00 EST) upcoming
    freezer.move_to("2026-01-09T17:00:00+00:00")
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.credit_hivernal_residentiel_cpc_d_event_begins")
    assert state is not None
    assert state.state == "2026-01-09T21:00:00+00:00"

    state = hass.states.get("sensor.credit_hivernal_residentiel_cpc_d_event_ends")
    assert state is not None
    assert state.state == "2026-01-10T01:00:00+00:00"


async def test_sensors_active_event(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Sensors expose the event in progress over the next one."""
    # 17:00 EST: the evening event is in progress
    freezer.move_to("2026-01-09T22:00:00+00:00")
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.credit_hivernal_residentiel_cpc_d_event_begins")
    assert state is not None
    assert state.state == "2026-01-09T21:00:00+00:00"


async def test_sensors_roll_over_at_boundary(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Sensors roll to the next event at the boundary, not the next poll."""
    # 19:59 EST, one minute before the 16:00-20:00 EST event ends
    freezer.move_to("2026-01-10T00:59:00+00:00")
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.credit_hivernal_residentiel_cpc_d_event_begins")
    assert state is not None
    assert state.state == "2026-01-09T21:00:00+00:00"

    # Cross the event end; the coordinator's boundary timer must fire
    freezer.move_to("2026-01-10T01:00:01+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.credit_hivernal_residentiel_cpc_d_event_begins")
    assert state is not None
    assert state.state == "2026-01-10T11:00:00+00:00"


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

    state = hass.states.get("sensor.credit_hivernal_residentiel_cpc_d_event_begins")
    assert state is not None
    assert state.state == STATE_UNKNOWN
