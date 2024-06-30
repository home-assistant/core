"""Tests for calendar platform."""

import datetime
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
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


@pytest.mark.freeze_time(datetime.datetime(2023, 6, 5, tzinfo=datetime.UTC))
async def test_calendar_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """State test of the calendar."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("calendar.test_mower_1")
    assert state is not None
    assert state.state == "off"


@pytest.mark.freeze_time(datetime.datetime(2023, 6, 5, 19, tzinfo=datetime.UTC))
async def test_calendar_state2(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """State test of the calendar."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("calendar.test_mower_1")
    assert state is not None
    assert state.state == "on"


@pytest.mark.freeze_time(datetime.datetime(2023, 6, 5, tzinfo=datetime.UTC))
@pytest.mark.parametrize(
    (
        "start_date",
        "end_date",
    ),
    [
        (
            datetime.datetime(2023, 6, 5, tzinfo=datetime.UTC),
            datetime.datetime(2023, 6, 12, tzinfo=datetime.UTC),
        ),
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
    """Snapshot test of the calendar."""
    await hass.config.async_set_time_zone("UTC")
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
