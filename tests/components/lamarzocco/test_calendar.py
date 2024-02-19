"""Tests for La Marzocco calendar."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

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
from homeassistant.util import dt as dt_util

from . import async_init_integration

from tests.common import MockConfigEntry


async def test_calendar_events(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the calendar."""

    test_time = datetime(2024, 1, 12, 11, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    freezer.move_to(test_time)

    await async_init_integration(hass, mock_config_entry)

    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"calendar.{serial_number}_auto_on_off_schedule")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry == snapshot

    events = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: f"calendar.{serial_number}_auto_on_off_schedule",
            EVENT_START_DATETIME: test_time,
            EVENT_END_DATETIME: test_time + timedelta(days=23),
        },
        blocking=True,
        return_response=True,
    )

    assert events == snapshot


@pytest.mark.parametrize(
    (
        "start_date",
        "end_date",
    ),
    [
        (datetime(2024, 2, 11, 6, 0), datetime(2024, 2, 18, 6, 0)),
        (datetime(2024, 2, 11, 7, 15), datetime(2024, 2, 18, 6, 0)),
        (datetime(2024, 2, 11, 9, 0), datetime(2024, 2, 18, 7, 15)),
        (datetime(2024, 2, 11, 9, 0), datetime(2024, 2, 18, 8, 0)),
        (datetime(2024, 2, 11, 9, 0), datetime(2024, 2, 18, 6, 0)),
        (datetime(2024, 2, 11, 6, 0), datetime(2024, 2, 18, 8, 0)),
    ],
)
async def test_calendar_edge_cases(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    start_date: datetime,
    end_date: datetime,
) -> None:
    """Test edge cases."""
    start_date = start_date.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end_date = end_date.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)

    # set schedule to be only on Sunday, 07:00 - 07:30
    mock_lamarzocco.schedule[2]["enable"] = "Disabled"
    mock_lamarzocco.schedule[4]["enable"] = "Disabled"
    mock_lamarzocco.schedule[5]["enable"] = "Disabled"
    mock_lamarzocco.schedule[6]["enable"] = "Enabled"
    mock_lamarzocco.schedule[6]["on"] = "07:00"
    mock_lamarzocco.schedule[6]["off"] = "07:30"

    await async_init_integration(hass, mock_config_entry)

    events = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: f"calendar.{mock_lamarzocco.serial_number}_auto_on_off_schedule",
            EVENT_START_DATETIME: start_date,
            EVENT_END_DATETIME: end_date,
        },
        blocking=True,
        return_response=True,
    )

    assert events == snapshot


async def test_no_calendar_events_global_disable(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Assert no events when global auto on/off is disabled."""

    mock_lamarzocco.current_status["global_auto"] = "Disabled"
    test_time = datetime(2024, 1, 12, 11, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    freezer.move_to(test_time)

    await async_init_integration(hass, mock_config_entry)

    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"calendar.{serial_number}_auto_on_off_schedule")
    assert state

    events = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: f"calendar.{serial_number}_auto_on_off_schedule",
            EVENT_START_DATETIME: test_time,
            EVENT_END_DATETIME: test_time + timedelta(days=23),
        },
        blocking=True,
        return_response=True,
    )
    assert events == snapshot
