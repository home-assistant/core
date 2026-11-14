"""Test the Birthday calendar."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.birthday.calendar import _ordinal
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.freeze_time("2025-01-10 12:00:00")

ENTITY_ID = "calendar.birthdays"


async def _get_events(
    hass: HomeAssistant, start: str, end: str
) -> list[dict[str, Any]]:
    """Return the events of the calendar in the given range."""
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": ENTITY_ID,
            "start_date_time": start,
            "end_date_time": end,
        },
        blocking=True,
        return_response=True,
    )
    return response[ENTITY_ID]["events"]


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (1, "1st"),
        (2, "2nd"),
        (3, "3rd"),
        (4, "4th"),
        (10, "10th"),
        (11, "11th"),
        (12, "12th"),
        (13, "13th"),
        (21, "21st"),
        (22, "22nd"),
        (23, "23rd"),
        (101, "101st"),
        (111, "111th"),
    ],
)
def test_ordinal(number: int, expected: str) -> None:
    """Test the ordinal suffixes."""
    assert _ordinal(number) == expected


@pytest.mark.usefixtures("init_integration")
async def test_next_event(hass: HomeAssistant) -> None:
    """Test the entity state shows the next birthday."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    # 29 Feb 2000 in a non leap year falls back to 1 March
    assert state.attributes["message"] == "🎂 Leap's 25th birthday"


@pytest.mark.usefixtures("init_integration")
async def test_events_in_range(hass: HomeAssistant) -> None:
    """Test the events returned for a whole year."""
    events = await _get_events(hass, "2025-01-01 00:00:00", "2025-12-31 23:59:59")

    assert [event["summary"] for event in events] == [
        "🎂 Leap's 25th birthday",
        "🎂 Bob's birthday",
        "🎂 Alice's 35th birthday",
    ]
    # Baby is born in 2025, so no event (age 0) in that year
    assert events[0]["start"] == "2025-03-01"
    assert events[0]["end"] == "2025-03-02"
    assert events[0]["description"] == "Leap turns 25."
    assert events[1].get("description") is None


@pytest.mark.usefixtures("init_integration")
async def test_events_age_one(hass: HomeAssistant) -> None:
    """Test a birthday is shown starting from the first year."""
    events = await _get_events(hass, "2026-05-01 00:00:00", "2026-05-31 23:59:59")

    assert [event["summary"] for event in events] == ["🎂 Baby's 1st birthday"]


@pytest.mark.usefixtures("init_integration")
async def test_events_leap_day(hass: HomeAssistant) -> None:
    """Test the real 29 February is used in a leap year."""
    events = await _get_events(hass, "2028-02-01 00:00:00", "2028-03-05 00:00:00")

    assert [(event["summary"], event["start"]) for event in events] == [
        ("🎂 Leap's 28th birthday", "2028-02-29"),
    ]


@pytest.mark.usefixtures("init_integration")
async def test_events_multiple_years(hass: HomeAssistant) -> None:
    """Test a range spanning more than one year."""
    events = await _get_events(hass, "2025-12-01 00:00:00", "2026-02-01 00:00:00")
    assert events == []

    events = await _get_events(hass, "2025-06-01 00:00:00", "2026-06-30 00:00:00")
    assert [event["start"] for event in events] == [
        "2025-06-15",
        "2026-03-01",
        "2026-03-10",
        "2026-05-20",
        "2026-06-15",
    ]


async def test_no_birthdays(
    hass: HomeAssistant, mock_empty_config_entry: MockConfigEntry
) -> None:
    """Test the calendar without birthdays has no next event."""
    mock_empty_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_empty_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "off"
    assert "message" not in state.attributes
    assert await _get_events(hass, "2025-01-01 00:00:00", "2025-12-31 23:59:59") == []
