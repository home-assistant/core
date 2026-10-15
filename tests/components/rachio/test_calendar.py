"""Tests for the Rachio calendar platform."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

CALENDAR_ENTITY_ID = "calendar.rachio_base_station_sn123456"

pytestmark = [
    pytest.mark.parametrize("init_integration", [Platform.CALENDAR], indirect=True),
    pytest.mark.usefixtures("init_integration"),
]


async def test_get_events_empty_schedule(
    hass: HomeAssistant,
    mock_rachio: MagicMock,
) -> None:
    """Test that get_events returns empty list when no events are scheduled."""
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "start_date_time": datetime(2026, 6, 1, tzinfo=UTC),
            "end_date_time": datetime(2026, 6, 30, tzinfo=UTC),
        },
        target={"entity_id": CALENDAR_ENTITY_ID},
        blocking=True,
        return_response=True,
    )

    assert response[CALENDAR_ENTITY_ID]["events"] == []
