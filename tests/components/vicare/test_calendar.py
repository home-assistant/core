"""Test ViCare circulation schedule calendar."""

from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from PyViCare.PyViCareUtils import PyViCareNotSupportedFeatureError

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    EVENT_END_DATETIME,
    EVENT_START_DATETIME,
    SERVICE_GET_EVENTS,
)
from homeassistant.components.vicare.calendar import ViCareCirculationScheduleCalendar
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util import dt as dt_util

from . import MODULE, setup_integration
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry

ENTITY_CIRCULATION_SCHEDULE = "calendar.model0_circulation_schedule"

_FIXTURES: list[Fixture] = [Fixture({"type:boiler"}, "vicare/Vitodens300W.json")]


def _get_calendar_entity(
    hass: HomeAssistant, entity_id: str
) -> ViCareCirculationScheduleCalendar:
    """Return the ViCareCirculationScheduleCalendar entity object for the entity_id."""
    component: EntityComponent[ViCareCirculationScheduleCalendar] = hass.data[
        CALENDAR_DOMAIN
    ]
    return next(
        e
        for e in component.entities
        if e.entity_id == entity_id and isinstance(e, ViCareCirculationScheduleCalendar)
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_circulation_schedule_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that circulation schedule slots are exposed as calendar events."""
    # 2024-01-01 is a Monday.
    monday = datetime(2024, 1, 1, tzinfo=dt_util.get_default_time_zone())
    freezer.move_to(monday)

    schedule = {
        "mon": [
            {"start": "06:00", "end": "22:00", "mode": "on", "position": 0},
            {"start": "22:00", "end": "24:00", "mode": "5/25-cycles", "position": 1},
        ],
        "tue": [],
        "wed": [],
        "thu": [],
        "fri": [],
        "sat": [],
        "sun": [],
    }
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(_FIXTURES).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.CALENDAR]),
    ):
        await setup_integration(hass, mock_config_entry)

    entity = _get_calendar_entity(hass, ENTITY_CIRCULATION_SCHEDULE)
    with patch.object(
        entity._api,
        "getDomesticHotWaterCirculationSchedule",
        return_value=schedule,
    ):
        await entity.async_update_ha_state(force_refresh=True)

    events = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: ENTITY_CIRCULATION_SCHEDULE,
            EVENT_START_DATETIME: monday,
            EVENT_END_DATETIME: monday + timedelta(hours=23, minutes=59),
        },
        blocking=True,
        return_response=True,
    )

    slots = events[ENTITY_CIRCULATION_SCHEDULE]["events"]
    assert len(slots) == 2
    assert slots[0]["summary"] == "on"
    assert slots[0]["start"] == monday.replace(hour=6, minute=0).isoformat()
    assert slots[0]["end"] == monday.replace(hour=22, minute=0).isoformat()
    assert slots[1]["summary"] == "5/25-cycles"
    assert slots[1]["start"] == monday.replace(hour=22, minute=0).isoformat()
    assert (
        slots[1]["end"]
        == (monday + timedelta(days=1)).replace(hour=0, minute=0).isoformat()
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_circulation_schedule_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the calendar has no events when the device reports no schedule."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(_FIXTURES).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.CALENDAR]),
    ):
        await setup_integration(hass, mock_config_entry)

    entity = _get_calendar_entity(hass, ENTITY_CIRCULATION_SCHEDULE)
    with patch.object(
        entity._api,
        "getDomesticHotWaterCirculationSchedule",
        side_effect=PyViCareNotSupportedFeatureError("not supported"),
    ):
        await entity.async_update_ha_state(force_refresh=True)

    state = hass.states.get(ENTITY_CIRCULATION_SCHEDULE)
    assert state.state == "off"
