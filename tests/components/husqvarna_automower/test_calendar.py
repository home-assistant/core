"""Tests for calendar platform."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    EVENT_END_DATETIME,
    EVENT_START_DATETIME,
    SERVICE_GET_EVENTS,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.freeze_time(datetime(2023, 6, 5, 12, tzinfo=UTC))
@pytest.mark.parametrize(
    (
        "start_date",
        "end_date",
    ),
    [
        (datetime(2024, 3, 2, 6, 0), datetime(2024, 3, 18, 6, 0)),
    ],
)
async def test_calendar_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    start_date: datetime,
    end_date: datetime,
) -> None:
    """Snapshot tesst of the calendars."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    await setup_integration(hass, mock_config_entry)
    events = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: "calendar.test_mower_1",
            EVENT_START_DATETIME: start_date,
            EVENT_END_DATETIME: end_date,
        },
        blocking=True,
        return_response=True,
    )

    assert events == snapshot
