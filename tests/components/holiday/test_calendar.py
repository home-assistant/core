"""Tests for calendar platform of Holiday integration."""

from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.holiday import calendar
from homeassistant.components.holiday.const import CONF_PROVINCE, DOMAIN
from homeassistant.const import CONF_COUNTRY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def assert_setup_calendar(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the calendar."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_COUNTRY: "CH", CONF_PROVINCE: "GE"},
        title="Switzerland, GE",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


async def test_holiday_calendar_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test HolidayCalendarEntity functionality."""
    freezer.move_to(datetime(2023, 1, 1, 12, tzinfo=dt_util.UTC))

    config_entry = await assert_setup_calendar(hass)
    entity = calendar.HolidayCalendarEntity(
        hass, "Switzerland, GE", "CH", "GE", config_entry.entry_id
    )
    entity.hass = hass

    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 1, 1)

    events = await entity.async_get_events(hass, start_date, end_date)

    assert len(events) == 1

    assert events[0].summary == "Neujahrestag"
    assert events[0].start == start_date.date()
    assert events[0].end == end_date.date() + timedelta(days=1)
    assert events[0].location == "Switzerland, GE"

    hass.config.language = "fr"
    entity = calendar.HolidayCalendarEntity(
        hass, "Switzerland, GE", "CH", "GE", config_entry.entry_id
    )

    events = await entity.async_get_events(hass, start_date, end_date)
    assert events[0].summary == "Nouvel An"


async def test_async_get_events(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test events in a specific time frame."""
    freezer.move_to(datetime(2023, 1, 1, 12, tzinfo=dt_util.UTC))

    await assert_setup_calendar(hass)

    entity_id = "calendar.switzerland_ge"
    assert entity_id in entity_registry.entities

    state = hass.states.get(entity_id)
    assert state is not None

    assert state.state == "on"

    assert state.attributes.get("message") == "Neujahrestag"
    assert state.attributes.get("start_time") == "2023-01-01 00:00:00"
    assert state.attributes.get("end_time") == "2023-01-02 00:00:00"
    assert state.attributes.get("location") == "Switzerland, GE"
