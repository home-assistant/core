"""Test for calendar data source."""

from datetime import timedelta

import pytest
import voluptuous as vol

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.data_source import async_get_data_source
import homeassistant.util.dt as dt_util

START = dt_util.now().isoformat()
END = (dt_util.now() + timedelta(days=1)).isoformat()


async def test_data_source(hass, hass_client):
    """Test the calendar data source with a demo calendar."""
    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()

    events = await async_get_data_source(
        hass,
        "calendar",
        {
            "type": "get_events",
            "entity_id": "calendar.calendar_1",
            "start": START,
            "end": END,
        },
    )
    assert [event.get("summary") for event in events] == ["Future Event"]


async def test_invalid_entity(hass, hass_client):
    """Test data source with an entity that does not exist."""
    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()

    with pytest.raises(vol.Invalid, match="Entity 'calendar.invalid' not found"):
        await async_get_data_source(
            hass,
            "calendar",
            {
                "type": "get_events",
                "entity_id": "calendar.invalid",
                "start": START,
                "end": END,
            },
        )


async def test_missing_required_fields(hass, hass_client):
    """Test behavior when required fields are missing."""
    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()

    with pytest.raises(vol.Invalid, match="required key not provided"):
        await async_get_data_source(
            hass,
            "calendar",
            {
                "type": "get_events",
                "entity_id": "calendar.calendar_1",
                "end": END,
            },
        )
