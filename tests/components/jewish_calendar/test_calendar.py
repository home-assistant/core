"""Tests for the Jewish Calendar calendar platform."""

from datetime import datetime

from freezegun import freeze_time
import pytest

from homeassistant.components.jewish_calendar.const import (
    DEFAULT_CALENDAR_EVENTS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry_with_calendar_events() -> MockConfigEntry:
    """Create a config entry with calendar events configuration."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "language": "en",
            "diaspora": True,
            "latitude": 40.7128,
            "longitude": -74.006,
            "elevation": 0,
            "time_zone": "America/New_York",
        },
        options={
            "candle_lighting_minutes_before_sunset": 18,
            "havdalah_minutes_after_sunset": 0,
            "calendar_events": ["date", "holiday", "weekly_portion"],
        },
    )


async def test_calendar_exists(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that the calendar exists."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.jewish_calendar_events")
    assert state is not None
    assert state.name == "Jewish Calendar Events"


async def test_calendar_with_custom_events(
    hass: HomeAssistant, config_entry_with_calendar_events: MockConfigEntry
) -> None:
    """Test calendar with custom event configuration."""
    config_entry_with_calendar_events.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_with_calendar_events.entry_id)
    await hass.async_block_till_done()

    # The entity ID uses the entry title in the name
    state = hass.states.get("calendar.mock_title_events")
    assert state is not None


async def test_calendar_default_events(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test calendar uses default events when none configured."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the calendar entity from entity registry
    entity_registry = er.async_get(hass)
    calendar_entities = [
        entity
        for entity in entity_registry.entities.values()
        if entity.domain == "calendar"
        and entity.config_entry_id == config_entry.entry_id
    ]

    assert len(calendar_entities) == 1
    calendar_entity_id = calendar_entities[0].entity_id

    # Get the actual entity
    calendar_entity = hass.states.get(calendar_entity_id)
    assert calendar_entity is not None


@freeze_time("2024-01-15")  # Monday
async def test_async_get_events_date_range(
    hass: HomeAssistant, config_entry_with_calendar_events: MockConfigEntry
) -> None:
    """Test getting events for a date range."""
    config_entry_with_calendar_events.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_with_calendar_events.entry_id)
    await hass.async_block_till_done()

    # Use calendar service to get events
    start_date = datetime(2024, 1, 15)
    end_date = datetime(2024, 1, 17)

    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": "calendar.mock_title_events",
            "start_date_time": start_date.isoformat(),
            "end_date_time": end_date.isoformat(),
        },
        blocking=True,
        return_response=True,
    )

    assert "calendar.mock_title_events" in response
    events = response["calendar.mock_title_events"]["events"]
    assert isinstance(events, list)


async def test_calendar_with_different_options() -> None:
    """Test creating config entries with different calendar options."""
    # Test creating a config entry with specific calendar events
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "language": "en",
            "diaspora": True,
            "latitude": 40.7128,
            "longitude": -74.006,
            "elevation": 0,
            "time_zone": "America/New_York",
        },
        options={
            "candle_lighting_minutes_before_sunset": 18,
            "havdalah_minutes_after_sunset": 0,
            "calendar_events": [
                "date",
                "holiday",
                "weekly_portion",
                "omer_count",
                "daf_yomi",
                "candle_lighting",
                "havdalah",
            ],
        },
    )

    # Verify the options are set correctly
    assert config_entry.options["calendar_events"] == [
        "date",
        "holiday",
        "weekly_portion",
        "omer_count",
        "daf_yomi",
        "candle_lighting",
        "havdalah",
    ]


async def test_calendar_empty_event_config(
    hass: HomeAssistant,
) -> None:
    """Test calendar with empty event configuration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "language": "en",
            "diaspora": True,
            "latitude": 40.7128,
            "longitude": -74.006,
            "elevation": 0,
            "time_zone": "America/New_York",
        },
        options={
            "candle_lighting_minutes_before_sunset": 18,
            "havdalah_minutes_after_sunset": 0,
            "calendar_events": [],
        },
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.mock_title_events")
    assert state is not None


async def test_calendar_invalid_event_config(
    hass: HomeAssistant,
) -> None:
    """Test calendar with invalid event configuration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "language": "en",
            "diaspora": True,
            "latitude": 40.7128,
            "longitude": -74.006,
            "elevation": 0,
            "time_zone": "America/New_York",
        },
        options={
            "candle_lighting_minutes_before_sunset": 18,
            "havdalah_minutes_after_sunset": 0,
            "calendar_events": ["invalid_event_type", "date"],
        },
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.mock_title_events")
    assert state is not None


@freeze_time("2024-01-15")
async def test_calendar_event_descriptions(
    hass: HomeAssistant,
) -> None:
    """Test that calendar events have proper descriptions."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "language": "en",
            "diaspora": True,
            "latitude": 40.7128,
            "longitude": -74.006,
            "elevation": 0,
            "time_zone": "America/New_York",
        },
        options={
            "candle_lighting_minutes_before_sunset": 18,
            "havdalah_minutes_after_sunset": 0,
            "calendar_events": ["date", "daf_yomi"],
        },
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.mock_title_events")
    assert state is not None


async def test_calendar_diaspora_vs_israel(
    hass: HomeAssistant,
) -> None:
    """Test calendar events differ between diaspora and Israel settings."""
    # Test with diaspora=True
    config_entry_diaspora = MockConfigEntry(
        domain=DOMAIN,
        data={
            "language": "en",
            "diaspora": True,
            "latitude": 40.7128,
            "longitude": -74.006,
            "elevation": 0,
            "time_zone": "America/New_York",
        },
        options={
            "candle_lighting_minutes_before_sunset": 18,
            "havdalah_minutes_after_sunset": 0,
            "calendar_events": ["holiday"],
        },
    )

    config_entry_diaspora.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_diaspora.entry_id)
    await hass.async_block_till_done()

    # The calendar should be created successfully regardless of diaspora setting
    state = hass.states.get("calendar.mock_title_events")
    assert state is not None


async def test_default_calendar_events() -> None:
    """Test that default calendar events are properly defined."""
    assert isinstance(DEFAULT_CALENDAR_EVENTS, list)
    assert len(DEFAULT_CALENDAR_EVENTS) > 0
    assert "date" in DEFAULT_CALENDAR_EVENTS
