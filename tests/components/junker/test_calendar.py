"""Tests for the Junker calendar."""

from datetime import timedelta

import pytest

from homeassistant.components.junker.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util


@pytest.mark.freeze_time("2026-11-10 20:00:00")
@pytest.mark.usefixtures("init_integration")
async def test_calendar_event(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the calendar exposes the next collection."""
    entity_id = entity_registry.async_get_entity_id(
        "calendar", DOMAIN, "test-municipality:all"
    )
    state = hass.states.get(entity_id)
    assert state.attributes["message"] == "Kitchen"
    assert state.attributes["start_time"].startswith("2026-11-11")


@pytest.mark.freeze_time("2026-11-10 20:00:00")
@pytest.mark.usefixtures("init_integration")
async def test_get_events(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test fetching the calendar events of a range."""
    entity_id = entity_registry.async_get_entity_id(
        "calendar", DOMAIN, "test-municipality:all"
    )
    start = dt_util.now()
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": entity_id,
            "start_date_time": start,
            "end_date_time": start + timedelta(days=3),
        },
        blocking=True,
        return_response=True,
    )
    assert len(response[entity_id]["events"]) == 2
