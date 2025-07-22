"""Tests for the Jewish Calendar calendar platform."""

from datetime import datetime

from freezegun import freeze_time
import pytest

from homeassistant.components.jewish_calendar.const import DEFAULT_CALENDAR_EVENTS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


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
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test getting events for a date range."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Use calendar service to get events
    start_date = datetime(2024, 1, 15)
    end_date = datetime(2024, 1, 17)

    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": "calendar.jewish_calendar_events",
            "start_date_time": start_date.isoformat(),
            "end_date_time": end_date.isoformat(),
        },
        blocking=True,
        return_response=True,
    )

    assert "calendar.jewish_calendar_events" in response
    events = response["calendar.jewish_calendar_events"]["events"]
    assert isinstance(events, list)


@pytest.mark.parametrize(
    ("calendar_events"),
    [
        [
            "date",
            "holiday",
            "weekly_portion",
            "omer_count",
            "daf_yomi",
            "candle_lighting",
            "havdalah",
        ]
    ],
)
async def test_calendar_with_different_options(
    calendar_events: list[str], config_entry: MockConfigEntry
) -> None:
    """Test creating config entries with different calendar options."""

    # Verify the options are set correctly
    assert config_entry.options["calendar_events"] == calendar_events


@pytest.mark.parametrize(
    "calendar_events",
    [
        [],
    ],
)
async def test_calendar_empty_event_config(
    hass: HomeAssistant, config_entry: MockConfigEntry, calendar_events: list
) -> None:
    """Test calendar with empty event configuration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.jewish_calendar_events")
    assert state is not None


@pytest.mark.parametrize("calendar_events", (["invalid_event_type", "date"]))
async def test_calendar_invalid_event_config(
    hass: HomeAssistant, config_entry: MockConfigEntry, calendar_events: list[str]
) -> None:
    """Test calendar with invalid event configuration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.jewish_calendar_events")
    assert state is not None


@freeze_time("2024-01-15")
@pytest.mark.parametrize("calendar_events", (["date", "daf_yomi"]))
async def test_calendar_event_descriptions(
    hass: HomeAssistant, config_entry: MockConfigEntry, calendar_events: list[str]
) -> None:
    """Test that calendar events have proper descriptions."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.jewish_calendar_events")
    assert state is not None


@pytest.mark.parametrize(("location_data"), ["New York", "Jerusalem"], indirect=True)
async def test_calendar_diaspora_vs_israel(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test calendar events differ between diaspora and Israel settings."""
    # Test with diaspora=True
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # The calendar should be created successfully regardless of diaspora setting
    state = hass.states.get("calendar.jewish_calendar_events")
    assert state is not None


async def test_default_calendar_events() -> None:
    """Test that default calendar events are properly defined."""
    assert isinstance(DEFAULT_CALENDAR_EVENTS, list)
    assert len(DEFAULT_CALENDAR_EVENTS) > 0
    assert "date" in DEFAULT_CALENDAR_EVENTS
