"""Tests for the DVLA calendar platform."""

from datetime import datetime
from typing import Any
from unittest.mock import patch

from homeassistant.components.dvla.const import CONF_CALENDARS, CONF_REG_NUMBER, DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

MOCK_SCHEMA: dict[str, Any] = {
    "components": {
        "schemas": {
            "Vehicle": {
                "properties": {
                    "registrationNumber": {
                        "type": "string",
                        "description": "Registration number",
                    },
                    "taxDueDate": {
                        "type": "string",
                        "format": "date",
                        "description": "Tax due date",
                    },
                    "motExpiryDate": {
                        "type": "string",
                        "format": "date",
                        "description": "Roadworthiness expiry date",
                    },
                    "dateOfLastV5CIssued": {
                        "type": "string",
                        "format": "date",
                        "description": "Date of last V5C issued",
                    },
                    "fuelType": {
                        "type": "string",
                        "description": "Fuel type",
                    },
                }
            }
        }
    }
}


async def setup_dvla_entry(
    hass: HomeAssistant,
    vehicle_data: dict[str, Any],
) -> str:
    """Set up the DVLA integration with mocked vehicle data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        data={
            CONF_REG_NUMBER: "AB12CDE",
            CONF_CALENDARS: ["None"],
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.dvla.async_get_schema",
            return_value=MOCK_SCHEMA,
        ),
        patch(
            "homeassistant.components.dvla.coordinator.DVLACoordinator._async_update_data",
            return_value=vehicle_data,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("calendar", DOMAIN, "ab12cde")

    assert entity_id is not None
    return entity_id


async def get_calendar_events(
    hass: HomeAssistant,
    entity_id: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Get calendar events from the calendar service."""
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            ATTR_ENTITY_ID: entity_id,
            "start_date_time": start.isoformat(),
            "end_date_time": end.isoformat(),
        },
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert entity_id in response

    events = response[entity_id]["events"]
    assert isinstance(events, list)

    return events


async def test_calendar_entity_is_created(hass: HomeAssistant) -> None:
    """Test calendar entity is created."""
    entity_id = await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "taxDueDate": "2026-03-01",
            "make": "FORD",
        },
    )

    state = hass.states.get(entity_id)

    assert state is not None


async def test_calendar_returns_date_events(hass: HomeAssistant) -> None:
    """Test calendar returns events for date fields."""
    entity_id = await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "taxDueDate": "2026-03-01",
            "motExpiryDate": "2026-05-10",
            "make": "FORD",
        },
    )

    events = await get_calendar_events(
        hass,
        entity_id,
        datetime(2026, 1, 1),
        datetime(2026, 12, 31),
    )

    assert len(events) == 2
    assert {event["start"] for event in events} == {
        "2026-03-01",
        "2026-05-10",
    }
    assert {event["summary"] for event in events} == {
        "Taxduedate - AB12CDE",
        "Motexpirydate - AB12CDE",
    }


async def test_calendar_filters_events_by_date_range(hass: HomeAssistant) -> None:
    """Test calendar filters events by requested date range."""
    entity_id = await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "taxDueDate": "2026-03-01",
            "motExpiryDate": "2026-05-10",
            "make": "FORD",
        },
    )

    events = await get_calendar_events(
        hass,
        entity_id,
        datetime(2026, 1, 1),
        datetime(2026, 4, 1),
    )

    assert len(events) == 1
    assert events[0]["start"] == "2026-03-01"
    assert events[0]["summary"] == "Taxduedate - AB12CDE"


async def test_calendar_ignores_past_invalid_and_non_date_values(
    hass: HomeAssistant,
) -> None:
    """Test calendar ignores past, invalid, and non-date values."""
    entity_id = await setup_dvla_entry(
        hass,
        {
            "registrationNumber": "AB12CDE",
            "taxDueDate": "2020-01-01",
            "motExpiryDate": "not-a-date",
            "dateOfLastV5CIssued": "2026-06-01",
            "fuelType": "PETROL",
            "make": "FORD",
        },
    )

    events = await get_calendar_events(
        hass,
        entity_id,
        datetime(2026, 1, 1),
        datetime(2026, 12, 31),
    )

    assert len(events) == 1
    assert events[0]["start"] == "2026-06-01"
    assert events[0]["summary"] == "Dateoflastv5Cissued - AB12CDE"
