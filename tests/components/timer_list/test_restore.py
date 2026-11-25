"""Tests for the timer list that keeps its timers across restarts."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from homeassistant.components.timer_list import (
    RestoreTimerListEntity,
    TimerListEvent,
    TimerListEventType,
    TimerStatus,
)
from homeassistant.components.timer_list.const import DATA_COMPONENT
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from . import create_mock_platform

TEST_ENTITY_ID = "timer_list.kitchen_timers"
NOW = "2026-11-25T12:00:00+00:00"


class KitchenTimerList(RestoreTimerListEntity):
    """A restoring timer list as an integration would define one."""

    _attr_name = "Kitchen timers"
    _attr_unique_id = "kitchen_timers"


def _stored(timer_id: str, status: str, **fields: Any) -> dict[str, Any]:
    """Return a stored timer created ten minutes before ``NOW``."""
    return {
        "timer_id": timer_id,
        "name": timer_id,
        "status": status,
        "created_duration": 900.0,
        "created_at": "2026-11-25T11:50:00+00:00",
        "total_duration": 900.0,
        "finishes_at": None,
        "paused_remaining": None,
        "ended_at": None,
    } | fields


async def _setup(
    hass: HomeAssistant, timers: list[dict[str, Any]]
) -> tuple[KitchenTimerList, list[TimerListEvent]]:
    """Set up the timer list with stored timers and record its events."""
    mock_restore_cache_with_extra_data(
        hass, [(State(TEST_ENTITY_ID, "1"), {"timers": timers})]
    )
    entity = KitchenTimerList()
    await create_mock_platform(hass, [entity])
    events: list[TimerListEvent] = []
    entity.async_subscribe_updates(events.append)
    return entity, events


@pytest.mark.freeze_time(NOW)
async def test_restore_timers(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test running and archived timers are restored, and still finish."""
    entity, events = await _setup(
        hass,
        [
            _stored("active", "active", finishes_at="2026-11-25T12:05:00+00:00"),
            _stored("paused", "paused", paused_remaining=120.0),
            _stored("cancelled", "cancelled", ended_at="2026-11-25T11:55:00+00:00"),
        ],
    )

    assert hass.states.get(TEST_ENTITY_ID).state == "1"
    timers = {timer.timer_id: timer for timer in entity.timers}
    assert timers["active"].status == TimerStatus.ACTIVE
    assert timers["active"].remaining_at(dt_util.utcnow()) == timedelta(minutes=5)
    assert timers["paused"].status == TimerStatus.PAUSED
    assert timers["paused"].paused_remaining == timedelta(minutes=2)
    assert timers["cancelled"].status == TimerStatus.CANCELLED
    assert events == []

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert [(event.event_type, event.item.timer_id) for event in events] == [
        (TimerListEventType.FINISHED, "active")
    ]
    assert hass.states.get(TEST_ENTITY_ID).state == "0"


@pytest.mark.freeze_time(NOW)
async def test_restore_overdue_timer(hass: HomeAssistant) -> None:
    """Test a timer that ran out while stopped is archived without an event."""
    entity, events = await _setup(
        hass,
        [_stored("overdue", "active", finishes_at="2026-11-25T11:58:00+00:00")],
    )

    assert hass.states.get(TEST_ENTITY_ID).state == "0"
    (timer,) = entity.timers
    assert timer.status == TimerStatus.FINISHED
    assert timer.finishes_at is None
    # When it ran out, not when it was restored
    assert timer.ended_at == dt_util.parse_datetime("2026-11-25T11:58:00+00:00")
    assert events == []


@pytest.mark.freeze_time(NOW)
async def test_restore_skips_invalid_timers(hass: HomeAssistant) -> None:
    """Test stored timers that cannot be read are left out."""
    entity, _ = await _setup(
        hass,
        [
            {"timer_id": "incomplete"},
            _stored("bad_status", "ringing"),
            _stored("bad_date", "paused", created_at="yesterday"),
            _stored("paused", "paused", paused_remaining=60.0),
        ],
    )

    assert [timer.timer_id for timer in entity.timers] == ["paused"]


@pytest.mark.freeze_time(NOW)
async def test_stored_data_round_trip(hass: HomeAssistant) -> None:
    """Test the stored timers are what is restored."""
    stored = [
        _stored("active", "active", finishes_at="2026-11-25T12:05:00+00:00"),
        _stored("paused", "paused", paused_remaining=120.5),
        _stored("finished", "finished", ended_at="2026-11-25T11:59:00+00:00"),
    ]
    entity, _ = await _setup(hass, stored)

    assert entity.extra_restore_state_data.as_dict() == {"timers": stored}


async def test_nothing_stored(hass: HomeAssistant) -> None:
    """Test a timer list without stored timers starts empty."""
    entity = KitchenTimerList()
    await create_mock_platform(hass, [entity])

    assert hass.data[DATA_COMPONENT].get_entity(TEST_ENTITY_ID) is entity
    assert entity.timers == []
    assert hass.states.get(TEST_ENTITY_ID).state == "0"
