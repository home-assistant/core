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

from . import WAKE_UP_SLEEP_ENTRY_IDS, async_init_integration

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

    test_time = datetime(2024, 1, 12, 11, tzinfo=dt_util.get_default_time_zone())
    freezer.move_to(test_time)

    await async_init_integration(hass, mock_config_entry)

    serial_number = mock_lamarzocco.serial_number

    for identifier in WAKE_UP_SLEEP_ENTRY_IDS:
        identifier = identifier.lower()
        state = hass.states.get(
            f"calendar.{serial_number}_auto_on_off_schedule_{identifier}"
        )
        assert state
        assert state == snapshot(
            name=f"state.{serial_number}_auto_on_off_schedule_{identifier}"
        )

        entry = entity_registry.async_get(state.entity_id)
        assert entry
        assert entry == snapshot(
            name=f"entry.{serial_number}_auto_on_off_schedule_{identifier}"
        )

        events = await hass.services.async_call(
            CALENDAR_DOMAIN,
            SERVICE_GET_EVENTS,
            {
                ATTR_ENTITY_ID: f"calendar.{serial_number}_auto_on_off_schedule_{identifier}",
                EVENT_START_DATETIME: test_time,
                EVENT_END_DATETIME: test_time + timedelta(days=23),
            },
            blocking=True,
            return_response=True,
        )

        assert events == snapshot(
            name=f"events.{serial_number}_auto_on_off_schedule_{identifier}"
        )


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
    start_date = start_date.replace(tzinfo=dt_util.get_default_time_zone())
    end_date = end_date.replace(tzinfo=dt_util.get_default_time_zone())

    await async_init_integration(hass, mock_config_entry)

    events = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: f"calendar.{mock_lamarzocco.serial_number}_auto_on_off_schedule_{WAKE_UP_SLEEP_ENTRY_IDS[1].lower()}",
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

    wake_up_sleep_entry_id = WAKE_UP_SLEEP_ENTRY_IDS[0]

    wake_up_sleep_entry = mock_lamarzocco.schedule.smart_wake_up_sleep.schedules_dict[
        wake_up_sleep_entry_id
    ]

    assert wake_up_sleep_entry
    wake_up_sleep_entry.enabled = False
    test_time = datetime(2024, 1, 12, 11, tzinfo=dt_util.get_default_time_zone())
    freezer.move_to(test_time)

    await async_init_integration(hass, mock_config_entry)

    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(
        f"calendar.{serial_number}_auto_on_off_schedule_{wake_up_sleep_entry_id.lower()}"
    )
    assert state

    events = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: f"calendar.{serial_number}_auto_on_off_schedule_{wake_up_sleep_entry_id.lower()}",
            EVENT_START_DATETIME: test_time,
            EVENT_END_DATETIME: test_time + timedelta(days=23),
        },
        blocking=True,
        return_response=True,
    )
    assert events == snapshot
