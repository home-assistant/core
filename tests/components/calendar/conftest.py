"""Test fixtures for calendar sensor platforms."""

from collections.abc import Generator
import datetime
import secrets
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.calendar import DOMAIN, CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test"


@pytest.fixture
async def set_time_zone(hass: HomeAssistant) -> None:
    """Set the time zone for the tests."""
    # Set our timezone to CST/Regina so we can check calculations
    # This keeps UTC-6 all year round
    await hass.config.async_set_time_zone("America/Regina")


class MockFlow(ConfigFlow):
    """Test flow."""


class MockCalendarEntity(CalendarEntity):
    """Test Calendar entity."""

    _attr_has_entity_name = True

    def __init__(self, name: str, events: list[CalendarEvent] | None = None) -> None:
        """Initialize entity."""
        self._attr_name = name.capitalize()
        self._events = events or []

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._events[0] if self._events else None

    def create_event(
        self,
        start: datetime.datetime,
        end: datetime.datetime,
        summary: str | None = None,
        description: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        """Create a new fake event, used by tests."""
        event = CalendarEvent(
            start=start,
            end=end,
            summary=summary if summary else f"Event {secrets.token_hex(16)}",
            description=description,
            location=location,
        )
        self._events.append(event)
        return event.as_dict()

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        assert start_date < end_date
        events = []
        for event in self._events:
            if event.start_datetime_local >= end_date:
                continue
            if event.end_datetime_local < start_date:
                continue
            events.append(event)
        return events


@pytest.fixture
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


@pytest.fixture(name="config_entry")
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry."""
    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def mock_setup_integration(
    hass: HomeAssistant,
    config_flow_fixture: None,
    test_entities: list[CalendarEntity],
) -> None:
    """Fixture to set up a mock integration."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> bool:
        await hass.config_entries.async_unload_platforms(
            config_entry, [Platform.CALENDAR]
        )
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
            async_unload_entry=async_unload_entry_init,
        ),
    )

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test event platform via config entry."""
        new_entities = create_test_entities()
        test_entities.clear()
        test_entities.extend(new_entities)
        async_add_entities(test_entities)

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )


@pytest.fixture(name="test_entities")
def mock_test_entities() -> list[MockCalendarEntity]:
    """Fixture that holdes the fake entities created during the test."""
    return []


def create_test_entities() -> list[MockCalendarEntity]:
    """Create test entities used during the test."""
    half_hour_from_now = dt_util.now() + datetime.timedelta(minutes=30)
    entity1 = MockCalendarEntity(
        "Calendar 1",
        [
            CalendarEvent(
                start=half_hour_from_now,
                end=half_hour_from_now + datetime.timedelta(minutes=60),
                summary="Future Event",
                description="Future Description",
                location="Future Location",
            )
        ],
    )
    entity1.async_get_events = AsyncMock(wraps=entity1.async_get_events)

    middle_of_event = dt_util.now() - datetime.timedelta(minutes=30)
    entity2 = MockCalendarEntity(
        "Calendar 2",
        [
            CalendarEvent(
                start=middle_of_event,
                end=middle_of_event + datetime.timedelta(minutes=60),
                summary="Current Event",
            )
        ],
    )
    entity2.async_get_events = AsyncMock(wraps=entity2.async_get_events)

    return [entity1, entity2]
