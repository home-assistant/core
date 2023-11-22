"""Tests for calendar platform of Holiday integration."""
from datetime import datetime

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    SERVICE_GET_EVENTS,
)
from homeassistant.components.holiday import calendar
from homeassistant.components.holiday.const import CONF_PROVINCE, DOMAIN
from homeassistant.const import CONF_COUNTRY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def test_holiday_calendar_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test HolidayCalendarEntity functionality."""
    freezer.move_to(datetime(2023, 1, 1, 12, tzinfo=dt_util.UTC))

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_COUNTRY: "US", CONF_PROVINCE: "AK"},
        title="United States, AK",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            "entity_id": "calendar.united_states_ak",
            "end_date_time": dt_util.now(),
        },
        blocking=True,
        return_response=True,
    )
    assert response == {
        "calendar.united_states_ak": {
            "events": [
                {
                    "start": "2023-01-01",
                    "end": "2023-01-02",
                    "summary": "New Year's Day",
                    "location": "United States, AK",
                }
            ]
        }
    }

    state = hass.states.get("calendar.united_states_ak")
    assert state is not None and state.state == "on"


async def test_default_language(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test default language."""
    freezer.move_to(datetime(2023, 1, 1, 12, tzinfo=dt_util.UTC))

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_COUNTRY: "FR", CONF_PROVINCE: "BL"},
        title="France, BL",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity = calendar.HolidayCalendarEntity(
        hass, "United States, AK", "US", "AK", config_entry.entry_id
    )
    assert entity._default_language == "en_US"

    # holidays has only "en" translations for Canada
    hass.config.language = "en"
    entity = calendar.HolidayCalendarEntity(
        hass, "Canada, AB", "CA", "AB", config_entry.entry_id
    )
    assert entity._default_language == "en"

    # Test French calendar with English language
    entity = calendar.HolidayCalendarEntity(
        hass, "France, BL", "FR", "BL", config_entry.entry_id
    )
    events = await entity.async_get_events(hass, dt_util.now(), dt_util.now())
    assert events[0].summary == "New Year's Day"

    # Test French calendar with French language
    hass.config.language = "fr"
    entity = calendar.HolidayCalendarEntity(
        hass, "France, BL", "FR", "BL", config_entry.entry_id
    )
    events = await entity.async_get_events(hass, dt_util.now(), dt_util.now())
    assert events[0].summary == "Jour de l'an"
