"""Test todo intents."""

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest

from homeassistant.components import calendar, conversation
from homeassistant.components.calendar import DOMAIN, intent as calendar_intent
from homeassistant.components.calendar.intent import (
    INTENT_CALENDAR_GET_EVENTS,
    CalendarGetEvents,
)
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_mock_service


@pytest.fixture(autouse=True)
async def setup_intents(hass: HomeAssistant) -> None:
    """Set up the intents."""
    assert await async_setup_component(hass, "homeassistant", {})
    await calendar_intent.async_setup_intents(hass)


@pytest.mark.parametrize(
    ("range_value"),
    [
        ("today"),
        ("week"),
    ],
)
async def test_calendar_get_events_intent(
    hass: HomeAssistant, range_value: str
) -> None:
    """Test the calendar get events intent."""
    calls = async_mock_service(
        hass,
        domain=calendar.DOMAIN,
        service=calendar.SERVICE_GET_EVENTS,
        schema=calendar.SERVICE_GET_EVENTS_SCHEMA,
        response={
            "calendar.test_calendar": {
                "events": [
                    {
                        "start": "2025-09-17",
                        "end": "2025-09-18",
                        "summary": "Home Assistant 12th birthday",
                        "description": "",
                    },
                    {
                        "start": "2025-09-17T14:00:00-05:00",
                        "end": "2025-09-18T15:00:00-05:00",
                        "summary": "Champagne",
                        "description": "",
                    },
                ]
            }
        },
        supports_response=SupportsResponse.ONLY,
    )

    now = dt_util.now()
    patch_now = patch.multiple(
        "homeassistant.util.dt",
        now=Mock(return_value=now),
    )
    patch_match_targets = patch(
        "homeassistant.helpers.intent.async_match_targets",
        return_value=Mock(
            is_match=True, states=[Mock(entity_id="calendar.test_calendar")]
        ),
    )

    with patch_now, patch_match_targets:
        response = await intent.async_handle(
            hass,
            DOMAIN,
            INTENT_CALENDAR_GET_EVENTS,
            {
                "calendar": {"value": "test_calendar"},
                "range": {"value": range_value},
            },
            assistant=conversation.DOMAIN,
        )

        assert len(calls) == 1
        call = calls[0]
        assert call.domain == calendar.DOMAIN
        assert call.service == calendar.SERVICE_GET_EVENTS
        assert call.data == {
            "entity_id": ["calendar.test_calendar"],
            "start_date_time": now,
            "end_date_time": (
                dt_util.start_of_local_day()
                + (timedelta(days=1) if range_value == "today" else timedelta(days=7))
            ),
        }

        assert response.speech_slots["events"] == [
            {
                "start": "2025-09-17",
                "end": "2025-09-18",
                "all_day": True,
                "summary": "Home Assistant 12th birthday",
                "description": "",
                "location": "",
                "recurring": None,
            },
            {
                "start": "2025-09-17T14:00:00-05:00",
                "end": "2025-09-18T15:00:00-05:00",
                "all_day": False,
                "summary": "Champagne",
                "description": "",
                "location": "",
                "recurring": None,
            },
        ]


async def test_calendar_get_events_intent_no_match(hass: HomeAssistant) -> None:
    """Test the calendar get events intent with no match."""
    with (
        patch(
            "homeassistant.helpers.intent.async_match_targets",
            return_value=Mock(is_match=False),
        ),
        pytest.raises(intent.MatchFailedError),
    ):
        await intent.async_handle(
            hass,
            DOMAIN,
            INTENT_CALENDAR_GET_EVENTS,
            {
                "calendar": {"value": "test_calendar"},
                "range": {"value": "today"},
            },
            assistant=conversation.DOMAIN,
        )


async def test_get_date_range() -> None:
    """Test _get_date_range method of CalendarGetEvents."""
    handler = CalendarGetEvents()

    # Test for "today"
    start, end = handler._get_date_range("today")
    assert start.date() == dt_util.now().date()
    assert end.date() == (dt_util.start_of_local_day() + timedelta(days=1)).date()

    # Test for "week"
    start, end = handler._get_date_range("week")
    assert start.date() == dt_util.now().date()
    assert end.date() == (dt_util.start_of_local_day() + timedelta(days=7)).date()

    # Test for invalid range value
    with pytest.raises(ValueError, match="Invalid range: invalid"):
        handler._get_date_range("invalid")
