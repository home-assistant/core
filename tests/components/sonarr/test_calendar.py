"""The tests for Sonarr calendar platform."""

from datetime import datetime
import json
from unittest.mock import MagicMock

from aiopyarr import SonarrCalendar
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    SERVICE_GET_EVENTS,
)
from homeassistant.components.sonarr.calendar import _get_calendar_event
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

ENTITY_ID = "calendar.sonarr"


def test_get_calendar_event_without_overview() -> None:
    """Test that episodes without an overview do not raise (real Sonarr omits it)."""
    raw = json.loads(load_fixture("sonarr/calendar.json"))[0]
    raw.pop("overview")

    event = _get_calendar_event(SonarrCalendar(raw))

    assert event.description is None
    assert event.summary == "Bob's Burgers - S04E11 - Easy Com-mercial, Easy Go-mercial"


@pytest.mark.parametrize(
    ("now", "expected_state"),
    [
        ("2014-01-27 01:45:00+00:00", STATE_ON),  # During the episode air window
        ("2014-01-27 03:00:00+00:00", STATE_OFF),  # After the episode aired
    ],
)
async def test_calendar_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_sonarr: MagicMock,
    now: str,
    expected_state: str,
) -> None:
    """Test the Sonarr calendar entity state."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to(now)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == expected_state


async def test_calendar_attributes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_sonarr: MagicMock,
) -> None:
    """Test the Sonarr calendar entity attributes for the active event."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2014-01-27 01:45:00+00:00")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes["all_day"] is False
    assert (
        state.attributes["message"]
        == "Bob's Burgers - S04E11 - Easy Com-mercial, Easy Go-mercial"
    )
    assert state.attributes["start_time"] == "2014-01-27 01:30:00"
    assert state.attributes["end_time"] == "2014-01-27 02:00:00"
    assert state.attributes["description"].startswith("To compete with fellow")


async def test_calendar_get_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sonarr: MagicMock,
) -> None:
    """Test the Sonarr calendar get_events service."""
    await hass.config.async_set_time_zone("UTC")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            "entity_id": ENTITY_ID,
            "start_date_time": datetime(2014, 1, 1).isoformat(),
            "end_date_time": datetime(2014, 2, 1).isoformat(),
        },
        blocking=True,
        return_response=True,
    )

    events = response[ENTITY_ID]["events"]
    assert len(events) == 1
    assert (
        events[0]["summary"]
        == "Bob's Burgers - S04E11 - Easy Com-mercial, Easy Go-mercial"
    )
    assert events[0]["start"] == "2014-01-27T01:30:00+00:00"
    assert events[0]["end"] == "2014-01-27T02:00:00+00:00"
    assert mock_sonarr.async_get_calendar.call_args.kwargs["include_series"] is True
