"""Test calendar platform for School Holiday integration."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.school_holiday.calendar import SchoolHolidayCalendarEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_CALENDAR_NAME, TEST_COUNTRY, TEST_ENTRY_ID, TEST_REGION

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify which platforms to test."""
    return [Platform.CALENDAR]


async def test_calendar_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_api_response,
) -> None:
    """Test calendar setup and entity registration."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that the calendar entity is registered.
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    calendar_entries = [e for e in entity_entries if e.domain == Platform.CALENDAR]
    assert len(calendar_entries) == 1

    entry = calendar_entries[0]
    assert entry.domain == Platform.CALENDAR


def test_calendar_entity_available() -> None:
    """Test calendar entity availability with successful last update."""
    coordinator = MagicMock()
    coordinator.last_update_success = True

    entity = SchoolHolidayCalendarEntity(
        coordinator, TEST_CALENDAR_NAME, TEST_COUNTRY, TEST_REGION, TEST_ENTRY_ID
    )

    assert entity.available is True


def test_calendar_entity_unavailable() -> None:
    """Test calendar entity availability with unsuccessful last update."""
    coordinator = MagicMock()
    coordinator.last_update_success = False

    entity = SchoolHolidayCalendarEntity(
        coordinator, TEST_CALENDAR_NAME, TEST_COUNTRY, TEST_REGION, TEST_ENTRY_ID
    )

    assert entity.available is False


def test_calendar_entity_attributes() -> None:
    """Test calendar entity attributes."""
    coordinator = MagicMock()

    entity = SchoolHolidayCalendarEntity(
        coordinator, TEST_CALENDAR_NAME, TEST_COUNTRY, TEST_REGION, TEST_ENTRY_ID
    )

    assert entity._attr_name == TEST_CALENDAR_NAME
    assert entity._country == TEST_COUNTRY
    assert entity._region == TEST_REGION
    assert entity.unique_id == f"{TEST_ENTRY_ID}_calendar"


def test_calendar_entity_with_school_holidays(mock_school_holiday_data) -> None:
    """Test calendar entity with school holidays."""
    coordinator = MagicMock()
    coordinator.data = mock_school_holiday_data

    entity = SchoolHolidayCalendarEntity(
        coordinator, TEST_CALENDAR_NAME, TEST_COUNTRY, TEST_REGION, TEST_ENTRY_ID
    )

    events = entity.events
    assert len(events) == 2

    # Verify that the calendar events match the mock data.
    for i, school_holiday in enumerate(mock_school_holiday_data):
        assert events[i]["summary"] == school_holiday["summary"]
        assert events[i]["start"] == school_holiday["start"]
        assert events[i]["end"] == school_holiday["end"]
        assert events[i]["description"] == school_holiday["description"]


def test_calendar_entity_without_school_holidays() -> None:
    """Test calendar entity without school holidays."""
    coordinator = MagicMock()
    coordinator.data = []

    entity = SchoolHolidayCalendarEntity(
        coordinator, TEST_CALENDAR_NAME, TEST_COUNTRY, TEST_REGION, TEST_ENTRY_ID
    )

    events = entity.events
    assert events == []
