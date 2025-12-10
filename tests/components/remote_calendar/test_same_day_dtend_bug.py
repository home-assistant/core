"""Test that reproduces the same-day DTEND bug."""

from datetime import datetime, timezone, timedelta
import pytest
import textwrap
from httpx import Response
import respx

from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import CALENDER_URL, TEST_ENTITY

from tests.common import MockConfigEntry


@pytest.mark.freeze_time(datetime(2025, 12, 8, 15, 0, tzinfo=timezone(timedelta(hours=1))))
@respx.mock
async def test_calendar_same_day_dtend_bug(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test calendar with same-day DTEND format.
    
    Some calendar providers (like CalendarLabs) use same-day DTEND format
    for all-day events where DTSTART and DTEND are the same date.
    This reproduces the bug where such calendars show 'off' instead of 'on'
    during the event.
    
    The bug occurs because active_after(now) doesn't handle same-day
    DTEND format correctly.
    """
    # Some calendar providers use same-day DTEND format: DTEND same as DTSTART
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=textwrap.dedent(
                """\
                BEGIN:VCALENDAR
                VERSION:2.0
                PRODID:-//Calendar Labs//Calendar 1.0//EN
                BEGIN:VEVENT
                UID:q4bugdkb4@calendarlabs.com
                DTSTART;VALUE=DATE:20251208
                DTEND;VALUE=DATE:20251208
                SUMMARY:Immaculate Conception Day
                DESCRIPTION:Visit https://calendarlabs.com/holidays/spain/immaculate-conception-day.php to know more about Immaculate Conception Day.
                LOCATION:Spain
                END:VEVENT
                END:VCALENDAR
                """
            ),
        )
    )
    
    await setup_integration(hass, config_entry)
    
    # At 15:00 CET on December 8th (during the holiday),
    # the calendar should show 'on' but shows 'off' without the fix
    state = hass.states.get(TEST_ENTITY)
    assert state
    
    # This assertion will fail with the original implementation
    # because active_after(now) doesn't handle same-day DTEND correctly
    assert state.state == STATE_ON, (
        "Holiday should be active during the day. "
        "Same-day DTEND format should be supported."
    )
    assert state.attributes["message"] == "Immaculate Conception Day"
