"""Tests for calendar platform of Holiday integration."""
from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    SERVICE_GET_EVENTS,
)
from homeassistant.components.holiday.const import CONF_PROVINCE, DOMAIN
from homeassistant.const import CONF_COUNTRY
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_holiday_calendar_entity(
    hass: HomeAssistant,
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

    await async_setup_component(hass, "calendar", {})
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
    assert state is not None
    assert state.state == "on"

    # Test holidays for the next year
    freezer.move_to(datetime(2023, 12, 31, 12, tzinfo=dt_util.UTC))

    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            "entity_id": "calendar.united_states_ak",
            "end_date_time": dt_util.now() + timedelta(days=1),
        },
        blocking=True,
        return_response=True,
    )
    assert response == {
        "calendar.united_states_ak": {
            "events": [
                {
                    "start": "2024-01-01",
                    "end": "2024-01-02",
                    "summary": "New Year's Day",
                    "location": "United States, AK",
                }
            ]
        }
    }


async def test_default_language(
    hass: HomeAssistant,
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

    # Test French calendar with English language
    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            "entity_id": "calendar.france_bl",
            "end_date_time": dt_util.now(),
        },
        blocking=True,
        return_response=True,
    )
    assert response == {
        "calendar.france_bl": {
            "events": [
                {
                    "start": "2023-01-01",
                    "end": "2023-01-02",
                    "summary": "New Year's Day",
                    "location": "France, BL",
                }
            ]
        }
    }

    # Test French calendar with French language
    hass.config.language = "fr"

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            "entity_id": "calendar.france_bl",
            "end_date_time": dt_util.now(),
        },
        blocking=True,
        return_response=True,
    )
    assert response == {
        "calendar.france_bl": {
            "events": [
                {
                    "start": "2023-01-01",
                    "end": "2023-01-02",
                    "summary": "Jour de l'an",
                    "location": "France, BL",
                }
            ]
        }
    }


async def test_no_language(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test language defaults to English if language not exist."""
    freezer.move_to(datetime(2023, 1, 1, 12, tzinfo=dt_util.UTC))

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_COUNTRY: "AL"},
        title="Albania",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            "entity_id": "calendar.albania",
            "end_date_time": dt_util.now(),
        },
        blocking=True,
        return_response=True,
    )
    assert response == {
        "calendar.albania": {
            "events": [
                {
                    "start": "2023-01-01",
                    "end": "2023-01-02",
                    "summary": "New Year's Day",
                    "location": "Albania",
                }
            ]
        }
    }


async def test_no_next_event(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test if there is no next event."""
    freezer.move_to(datetime(2023, 1, 1, 12, tzinfo=dt_util.UTC))

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_COUNTRY: "DE"},
        title="Germany",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Move time to out of reach
    freezer.move_to(datetime(dt_util.now().year + 5, 1, 1, 12, tzinfo=dt_util.UTC))
    async_fire_time_changed(hass)

    state = hass.states.get("calendar.germany")
    assert state is not None
    assert state.state == "off"
    assert state.attributes == {"friendly_name": "Germany"}


async def test_language_not_exist(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test when language doesn't exist it will fallback to country default language."""

    hass.config.language = "nb"  # Norweigan language "Norks bokmål"
    hass.config.country = "NO"

    freezer.move_to(datetime(2023, 1, 1, 12, tzinfo=dt_util.UTC))

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_COUNTRY: "NO"},
        title="Norge",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.norge")
    assert state is not None
    assert state.state == "on"
    assert state.attributes == {
        "friendly_name": "Norge",
        "all_day": True,
        "description": "",
        "end_time": "2023-01-02 00:00:00",
        "location": "Norge",
        "message": "Første nyttårsdag",
        "start_time": "2023-01-01 00:00:00",
    }

    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            "entity_id": "calendar.norge",
            "end_date_time": dt_util.now(),
        },
        blocking=True,
        return_response=True,
    )
    assert response == {
        "calendar.norge": {
            "events": [
                {
                    "start": "2023-01-01",
                    "end": "2023-01-02",
                    "summary": "Første nyttårsdag",
                    "location": "Norge",
                }
            ]
        }
    }

    # Test with English as exist as optional language for Norway
    hass.config.language = "en"
    hass.config.country = "NO"
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            "entity_id": "calendar.norge",
            "end_date_time": dt_util.now(),
        },
        blocking=True,
        return_response=True,
    )
    assert response == {
        "calendar.norge": {
            "events": [
                {
                    "start": "2023-01-01",
                    "end": "2023-01-02",
                    "summary": "New Year's Day",
                    "location": "Norge",
                }
            ]
        }
    }
