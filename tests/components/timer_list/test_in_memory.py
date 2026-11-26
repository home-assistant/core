"""Tests for the in-memory timer list."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.timer_list import (
    InMemoryTimerListEntity,
    TimerListEntity,
    TimerListEvent,
    TimerListEventType,
)
from homeassistant.components.timer_list.const import DATA_COMPONENT, DOMAIN
from homeassistant.components.timer_list.in_memory import MAX_ARCHIVED_TIMERS
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import create_mock_platform

TEST_ENTITY_ID = "timer_list.kitchen_timers"


class KitchenTimerList(InMemoryTimerListEntity):
    """An in-memory timer list as an integration would define one."""

    _attr_name = "Kitchen timers"
    _attr_unique_id = "kitchen_timers"


@pytest.fixture
async def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an in-memory timer list."""
    return await create_mock_platform(hass, [KitchenTimerList()])


@pytest.fixture
def entity(hass: HomeAssistant, config_entry: MockConfigEntry) -> TimerListEntity:
    """Return the in-memory timer list."""
    return hass.data[DATA_COMPONENT].get_entity(TEST_ENTITY_ID)


@pytest.fixture
def events(entity: TimerListEntity) -> list[TimerListEvent]:
    """Record the timer list's change events."""
    events: list[TimerListEvent] = []
    entity.async_subscribe_updates(events.append)
    return events


async def _call(
    hass: HomeAssistant, service: str, **fields: Any
) -> dict[str, Any] | None:
    """Call an action on the timer list and return its response, if any."""
    result = await hass.services.async_call(
        DOMAIN,
        service,
        fields,
        target={TargetKey.ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
        return_response=service in ("create_timer", "get_timers"),
    )
    return result[TEST_ENTITY_ID] if result else None


async def _create_timer(hass: HomeAssistant, seconds: int = 60) -> str:
    """Create a timer and return its id."""
    result = await _call(hass, "create_timer", duration={"seconds": seconds})
    assert result is not None
    return result["timer_id"]


async def _get_timers(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return the serialized timers."""
    result = await _call(hass, "get_timers")
    assert result is not None
    return result["timers"]


def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: int) -> None:
    """Move time forward and run the timers that are due."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)


@pytest.mark.usefixtures("entity")
async def test_timer_finishes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    events: list[TimerListEvent],
) -> None:
    """Test a timer finishes and is archived when its time is up."""
    await _create_timer(hass, 60)
    assert hass.states.get(TEST_ENTITY_ID).state == "1"

    _tick(hass, freezer, 59)
    await hass.async_block_till_done()
    assert hass.states.get(TEST_ENTITY_ID).state == "1"

    _tick(hass, freezer, 1)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == "0"
    assert [event.event_type for event in events] == [
        TimerListEventType.CREATED,
        TimerListEventType.FINISHED,
    ]
    timer = (await _get_timers(hass))[0]
    assert timer["status"] == "finished"
    assert timer["ended_at"] is not None
    assert timer["finishes_at"] is None


@pytest.mark.usefixtures("entity")
async def test_paused_timer_does_not_finish(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a paused timer keeps its remaining time until it is resumed."""
    timer_id = await _create_timer(hass, 60)
    _tick(hass, freezer, 20)
    await _call(hass, "pause_timer", timer_id=timer_id)

    _tick(hass, freezer, 120)
    await hass.async_block_till_done()
    timer = (await _get_timers(hass))[0]
    assert timer["status"] == "paused"
    assert timer["paused_remaining"] == 40
    assert timer["finishes_at"] is None

    await _call(hass, "unpause_timer", timer_id=timer_id)
    _tick(hass, freezer, 39)
    await hass.async_block_till_done()
    assert (await _get_timers(hass))[0]["status"] == "active"

    _tick(hass, freezer, 1)
    await hass.async_block_till_done()
    assert (await _get_timers(hass))[0]["status"] == "finished"


@pytest.mark.usefixtures("entity")
async def test_add_and_subtract_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, events: list[TimerListEvent]
) -> None:
    """Test adding and subtracting time moves the finish time."""
    timer_id = await _create_timer(hass, 60)

    await _call(hass, "add_time", timer_id=timer_id, duration={"seconds": 60})
    timer = (await _get_timers(hass))[0]
    assert timer["remaining"] == 120
    # "The 1 minute timer" must keep matching after time is added.
    assert timer["created_duration"] == 60
    assert timer["total_duration"] == 120

    await _call(hass, "subtract_time", timer_id=timer_id, duration={"seconds": 90})
    timer = (await _get_timers(hass))[0]
    assert timer["remaining"] == 30
    assert timer["created_duration"] == 60
    # The progress total is never lowered.
    assert timer["total_duration"] == 120
    assert [event.delta for event in events[1:]] == [
        timedelta(seconds=60),
        timedelta(seconds=-90),
    ]

    _tick(hass, freezer, 30)
    await hass.async_block_till_done()
    assert (await _get_timers(hass))[0]["status"] == "finished"


@pytest.mark.usefixtures("entity", "freezer")
async def test_add_time_to_paused_timer(hass: HomeAssistant) -> None:
    """Test adding time to a paused timer changes its frozen remaining time."""
    timer_id = await _create_timer(hass, 60)
    await _call(hass, "pause_timer", timer_id=timer_id)

    await _call(hass, "add_time", timer_id=timer_id, duration={"seconds": 30})

    timer = (await _get_timers(hass))[0]
    assert timer["status"] == "paused"
    assert timer["paused_remaining"] == 90
    assert timer["total_duration"] == 90


@pytest.mark.usefixtures("entity")
@pytest.mark.parametrize(
    ("setup_services", "seconds", "added", "remaining", "total"),
    [
        pytest.param([], 120, 60, 179.4, 180, id="active"),
        pytest.param(["pause_timer"], 60, 1, 60.4, 61, id="paused"),
    ],
)
async def test_add_time_rounds_total_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_services: list[str],
    seconds: int,
    added: int,
    remaining: float,
    total: int,
) -> None:
    """Test adding time rounds the total up to whole seconds."""
    timer_id = await _create_timer(hass, seconds)
    freezer.tick(timedelta(seconds=0.6))
    for service in setup_services:
        await _call(hass, service, timer_id=timer_id)

    await _call(hass, "add_time", timer_id=timer_id, duration={"seconds": added})

    timer = (await _get_timers(hass))[0]
    assert timer["remaining"] == pytest.approx(remaining)
    assert timer["total_duration"] == total


@pytest.mark.usefixtures("entity")
@pytest.mark.parametrize(
    "setup_services",
    [
        pytest.param([], id="active"),
        pytest.param(["pause_timer"], id="paused"),
    ],
)
async def test_subtract_more_than_remaining_finishes_timer(
    hass: HomeAssistant, events: list[TimerListEvent], setup_services: list[str]
) -> None:
    """Test subtracting more time than is left finishes the timer."""
    timer_id = await _create_timer(hass, 60)
    for service in setup_services:
        await _call(hass, service, timer_id=timer_id)

    await _call(hass, "subtract_time", timer_id=timer_id, duration={"seconds": 120})

    assert hass.states.get(TEST_ENTITY_ID).state == "0"
    assert events[-1].event_type == TimerListEventType.FINISHED
    assert (await _get_timers(hass))[0]["status"] == "finished"


@pytest.mark.usefixtures("entity")
@pytest.mark.parametrize(
    "setup_services",
    [
        pytest.param([], id="active"),
        pytest.param(["pause_timer"], id="paused"),
    ],
)
async def test_finish_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    events: list[TimerListEvent],
    setup_services: list[str],
) -> None:
    """Test finishing a timer early archives it and cancels its schedule."""
    timer_id = await _create_timer(hass, 60)
    for service in setup_services:
        await _call(hass, service, timer_id=timer_id)

    await _call(hass, "finish_timer", timer_id=timer_id)
    _tick(hass, freezer, 120)
    await hass.async_block_till_done()

    finished = [e for e in events if e.event_type == TimerListEventType.FINISHED]
    assert len(finished) == 1
    assert (await _get_timers(hass))[0]["status"] == "finished"


@pytest.mark.usefixtures("entity")
async def test_cancel_timer(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, events: list[TimerListEvent]
) -> None:
    """Test a cancelled timer is archived and never finishes."""
    timer_id = await _create_timer(hass, 60)

    await _call(hass, "cancel_timer", timer_id=timer_id)
    _tick(hass, freezer, 120)
    await hass.async_block_till_done()

    assert [event.event_type for event in events] == [
        TimerListEventType.CREATED,
        TimerListEventType.CANCELLED,
    ]
    assert (await _get_timers(hass))[0]["status"] == "cancelled"


@pytest.mark.usefixtures("entity")
async def test_remove_timer(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, events: list[TimerListEvent]
) -> None:
    """Test a removed timer is gone and never finishes."""
    timer_id = await _create_timer(hass, 60)

    await _call(hass, "remove_timer", timer_id=timer_id)
    _tick(hass, freezer, 120)
    await hass.async_block_till_done()

    assert [event.event_type for event in events] == [
        TimerListEventType.CREATED,
        TimerListEventType.REMOVED,
    ]
    assert await _get_timers(hass) == []


@pytest.mark.usefixtures("entity")
@pytest.mark.parametrize(
    ("archive_service", "service", "fields"),
    [
        pytest.param("cancel_timer", "cancel_timer", {}, id="cancel_cancelled"),
        pytest.param("cancel_timer", "finish_timer", {}, id="finish_cancelled"),
        pytest.param("finish_timer", "cancel_timer", {}, id="cancel_finished"),
        pytest.param("cancel_timer", "pause_timer", {}, id="pause_cancelled"),
        pytest.param("cancel_timer", "unpause_timer", {}, id="unpause_cancelled"),
        pytest.param(
            "cancel_timer",
            "add_time",
            {"duration": {"seconds": 30}},
            id="add_time_cancelled",
        ),
        pytest.param(
            "finish_timer",
            "subtract_time",
            {"duration": {"seconds": 30}},
            id="subtract_time_finished",
        ),
    ],
)
async def test_archived_timer_is_left_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    events: list[TimerListEvent],
    archive_service: str,
    service: str,
    fields: dict[str, Any],
) -> None:
    """Test actions on a finished or cancelled timer change nothing."""
    timer_id = await _create_timer(hass)
    await _call(hass, archive_service, timer_id=timer_id)
    before = await _get_timers(hass)
    event_count = len(events)

    freezer.tick(timedelta(seconds=5))
    await _call(hass, service, timer_id=timer_id, **fields)

    assert await _get_timers(hass) == before
    assert len(events) == event_count


@pytest.mark.usefixtures("entity", "freezer")
@pytest.mark.parametrize(
    ("service", "fields"),
    [
        pytest.param("unpause_timer", {}, id="unpause_active"),
        pytest.param("add_time", {"duration": {"seconds": 0}}, id="add_zero"),
        pytest.param("subtract_time", {"duration": {"seconds": 0}}, id="subtract_zero"),
    ],
)
async def test_action_without_effect(
    hass: HomeAssistant,
    events: list[TimerListEvent],
    service: str,
    fields: dict[str, Any],
) -> None:
    """Test actions that do not apply to an active timer change nothing."""
    timer_id = await _create_timer(hass)
    before = await _get_timers(hass)

    await _call(hass, service, timer_id=timer_id, **fields)

    assert await _get_timers(hass) == before
    assert len(events) == 1


@pytest.mark.usefixtures("entity")
async def test_pause_paused_timer(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, events: list[TimerListEvent]
) -> None:
    """Test pausing a paused timer keeps its frozen remaining time."""
    timer_id = await _create_timer(hass, 60)
    await _call(hass, "pause_timer", timer_id=timer_id)

    _tick(hass, freezer, 10)
    await _call(hass, "pause_timer", timer_id=timer_id)

    assert (await _get_timers(hass))[0]["paused_remaining"] == 60
    assert len(events) == 2


@pytest.mark.usefixtures("entity")
async def test_archive_limit(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, events: list[TimerListEvent]
) -> None:
    """Test only the most recently archived timers are kept."""
    active_id = await _create_timer(hass, 3600)
    archived_ids = []
    for _ in range(MAX_ARCHIVED_TIMERS + 1):
        timer_id = await _create_timer(hass)
        await _call(hass, "cancel_timer", timer_id=timer_id)
        archived_ids.append(timer_id)
        freezer.tick(timedelta(seconds=1))

    timer_ids = {timer["timer_id"] for timer in await _get_timers(hass)}
    assert timer_ids == {active_id, *archived_ids[1:]}
    assert events[-1].event_type == TimerListEventType.REMOVED
    assert events[-1].item.timer_id == archived_ids[0]


@pytest.mark.usefixtures("entity")
@pytest.mark.parametrize(
    ("service", "fields"),
    [
        pytest.param("pause_timer", {}, id="pause_timer"),
        pytest.param("unpause_timer", {}, id="unpause_timer"),
        pytest.param("cancel_timer", {}, id="cancel_timer"),
        pytest.param("finish_timer", {}, id="finish_timer"),
        pytest.param("add_time", {"duration": {"seconds": 5}}, id="add_time"),
        pytest.param("remove_timer", {}, id="remove_timer"),
    ],
)
async def test_unknown_timer(
    hass: HomeAssistant, service: str, fields: dict[str, Any]
) -> None:
    """Test actions on an unknown timer id raise a translated error."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await _call(hass, service, timer_id="unknown", **fields)

    assert exc_info.value.translation_key == "timer_not_found"
    assert exc_info.value.translation_placeholders == {"timer_id": "unknown"}


async def test_removing_entity_cancels_timers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    events: list[TimerListEvent],
) -> None:
    """Test timers do not finish after the entity is removed."""
    await _create_timer(hass, 60)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    _tick(hass, freezer, 120)
    await hass.async_block_till_done()

    assert [event.event_type for event in events] == [TimerListEventType.CREATED]
