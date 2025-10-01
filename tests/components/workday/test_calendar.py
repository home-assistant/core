"""Tests for calendar platform of Workday integration."""

from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    EVENT_END_DATETIME,
    EVENT_START_DATETIME,
    EVENT_SUMMARY,
    SERVICE_GET_EVENTS,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import TEST_CONFIG_WITH_PROVINCE, init_integration

from tests.common import async_fire_time_changed

ATTR_END = "end"
ATTR_START = "start"


@pytest.mark.parametrize(
    "time_zone", ["Asia/Tokyo", "Europe/Berlin", "America/Chicago", "US/Hawaii"]
)
async def test_holiday_calendar_entity(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    time_zone: str,
) -> None:
    """Test HolidayCalendarEntity functionality."""
    await hass.config.async_set_time_zone(time_zone)
    zone = await dt_util.async_get_time_zone(time_zone)
    freezer.move_to(datetime(2023, 1, 1, 0, 1, 1, tzinfo=zone))  # New Years Day
    await init_integration(hass, TEST_CONFIG_WITH_PROVINCE)

    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: "calendar.workday_sensor_calendar",
            EVENT_START_DATETIME: dt_util.now(),
            EVENT_END_DATETIME: dt_util.now() + timedelta(days=10, hours=1),
        },
        blocking=True,
        return_response=True,
    )
    assert {
        ATTR_END: "2023-01-02",
        ATTR_START: "2023-01-01",
        EVENT_SUMMARY: "Workday Sensor",
    } not in response["calendar.workday_sensor_calendar"]["events"]
    assert {
        ATTR_END: "2023-01-04",
        ATTR_START: "2023-01-03",
        EVENT_SUMMARY: "Workday Sensor",
    } in response["calendar.workday_sensor_calendar"]["events"]

    state = hass.states.get("calendar.workday_sensor_calendar")
    assert state is not None
    assert state.state == "off"

    freezer.move_to(
        datetime(2023, 1, 2, 0, 1, 1, tzinfo=zone)
    )  # Day after New Years Day
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.workday_sensor_calendar")
    assert state is not None
    assert state.state == "on"

    freezer.move_to(datetime(2023, 1, 7, 0, 1, 1, tzinfo=zone))  # Workday
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.workday_sensor_calendar")
    assert state is not None
    assert state.state == "off"
