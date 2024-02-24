"""Tests for calendar platform of Moon integration."""
from datetime import datetime

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    SERVICE_GET_EVENTS,
)
from homeassistant.components.moon.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def test_moon_calendar_entity(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test MoonCalendarEntity functionality."""
    freezer.move_to(datetime(2024, 1, 11, 12, tzinfo=dt_util.UTC))

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Moon",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await async_setup_component(hass, "calendar", {})
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            "entity_id": "calendar.moon",
            "start_date_time": "2024-01-11 00:00:00",
            "end_date_time": "2024-01-11 00:00:00",
        },
        blocking=True,
        return_response=True,
    )
    assert response == {
        "calendar.moon": {
            "events": [
                {
                    "start": "2024-01-11",
                    "end": "2024-01-12",
                    "summary": "New moon",
                }
            ]
        }
    }

    state = hass.states.get("calendar.moon")
    assert state is not None
    assert state.state == "on"
    assert state.attributes == {
        "message": "New moon",
        "all_day": True,
        "start_time": "2024-01-11 00:00:00",
        "end_time": "2024-01-12 00:00:00",
        "location": "",
        "description": "",
        "friendly_name": "Moon",
    }
