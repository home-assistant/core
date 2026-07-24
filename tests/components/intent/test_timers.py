"""Tests for intent timers."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from homeassistant.components.intent import DOMAIN
from homeassistant.components.intent.timers import (
    TimerNotFoundError,
    TimersNotSupportedError,
    _round_time,
    async_device_supports_timers,
)
from homeassistant.components.local_timer_list import LocalTimerListEntity
from homeassistant.components.timer_list import (
    DATA_COMPONENT as TIMER_LIST_DATA_COMPONENT,
    DOMAIN as TIMER_LIST_DOMAIN,
    TimerItem,
    TimerListEntity,
    TimerListEvent,
    TimerListEventType,
    TimerStatus,
)
from homeassistant.const import ATTR_NAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er, intent
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

# Observers receive the entity's raw TimerListEvent, exactly as satellite
# integrations do when they subscribe to their device's timer_list entity.
type _TimerObserver = Callable[[TimerListEvent], None]


def _remaining_seconds(item: TimerItem) -> int:
    """Return the whole seconds left on a timer right now."""
    return round(item.remaining_at(dt_util.utcnow()).total_seconds())


@pytest.fixture
async def init_components(hass: HomeAssistant) -> None:
    """Initialize required components for tests."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, DOMAIN, {})


def _make_timer_device_id(hass: HomeAssistant) -> str:
    """Create a real device to host a timer_list entity and return its id."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("test", entry.entry_id)},
    )
    return device.id


async def _register_timer_device(
    hass: HomeAssistant, device_id: str, observer: _TimerObserver | None = None
) -> CALLBACK_TYPE | None:
    """Give a device a timer_list entity and optionally observe its events.

    Mirrors what a satellite integration does: it creates a timer_list entity
    for the device and subscribes to it.
    """
    component = hass.data[TIMER_LIST_DATA_COMPONENT]
    await component.async_add_entities(
        [LocalTimerListEntity(name=f"{device_id} Timers", unique_id=device_id)]
    )
    # The list is resolved by device association, so link it to the device.
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        TIMER_LIST_DOMAIN, TIMER_LIST_DOMAIN, device_id
    )
    assert entity_id is not None
    entity_registry.async_update_entity(entity_id, device_id=device_id)

    if observer is None:
        return None

    entity = hass.data[TIMER_LIST_DATA_COMPONENT].get_entity(entity_id)
    assert entity is not None
    return entity.async_subscribe_updates(observer)


def _get_timer_entity(hass: HomeAssistant, device_id: str) -> TimerListEntity:
    """Return the timer_list entity created for a device."""
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        TIMER_LIST_DOMAIN, TIMER_LIST_DOMAIN, device_id
    )
    assert entity_id is not None
    timer_entity = hass.data[TIMER_LIST_DATA_COMPONENT].get_entity(entity_id)
    assert timer_entity is not None
    return timer_entity


async def test_start_finish_timer(hass: HomeAssistant, init_components) -> None:
    """Test starting a timer and having it finish."""
    device_id = _make_timer_device_id(hass)
    timer_name = "test timer"
    started_event = asyncio.Event()
    finished_event = asyncio.Event()

    timer_id: str | None = None

    @callback
    def handle_timer(event: TimerListEvent) -> None:
        nonlocal timer_id
        item = event.item

        assert item.name == timer_name
        assert item.duration == timedelta(0)
        assert _remaining_seconds(item) == 0

        if event.event_type == TimerListEventType.STARTED:
            timer_id = item.timer_id
            started_event.set()
        elif event.event_type == TimerListEventType.FINISHED:
            assert item.timer_id == timer_id
            finished_event.set()

    await _register_timer_device(hass, device_id, handle_timer)

    # A device that has been registered to handle timers is required
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {
            "name": {"value": timer_name},
            "seconds": {"value": 0},
        },
        device_id=device_id,
    )

    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await asyncio.gather(started_event.wait(), finished_event.wait())


async def test_cancel_timer(hass: HomeAssistant, init_components) -> None:
    """Test cancelling a timer."""
    device_id = _make_timer_device_id(hass)
    timer_name: str | None = None
    started_event = asyncio.Event()
    cancelled_event = asyncio.Event()

    timer_id: str | None = None

    @callback
    def handle_timer(event: TimerListEvent) -> None:
        nonlocal timer_id
        item = event.item

        assert item.duration == timedelta(hours=1, minutes=2, seconds=3)

        if timer_name is not None:
            assert item.name == timer_name

        if event.event_type == TimerListEventType.STARTED:
            timer_id = item.timer_id
            assert _remaining_seconds(item) == int(item.duration.total_seconds())
            started_event.set()
        elif event.event_type == TimerListEventType.CANCELLED:
            assert item.timer_id == timer_id
            assert _remaining_seconds(item) == 0
            cancelled_event.set()

    await _register_timer_device(hass, device_id, handle_timer)

    # Cancel by starting time
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {
            "hours": {"value": 1},
            "minutes": {"value": 2},
            "seconds": {"value": 3},
        },
        device_id=device_id,
    )

    async with asyncio.timeout(1):
        await started_event.wait()

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {
            "start_hours": {"value": 1},
            "start_minutes": {"value": 2},
            "start_seconds": {"value": 3},
        },
        device_id=device_id,
    )

    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await cancelled_event.wait()

    # Cancel by name
    timer_name = "test timer"
    started_event.clear()
    cancelled_event.clear()

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {
            "name": {"value": timer_name},
            "hours": {"value": 1},
            "minutes": {"value": 2},
            "seconds": {"value": 3},
        },
        device_id=device_id,
    )

    async with asyncio.timeout(1):
        await started_event.wait()

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {"name": {"value": timer_name}},
        device_id=device_id,
    )

    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await cancelled_event.wait()

    # Cancel the device's only timer without any constraints
    timer_name = None
    started_event.clear()
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {
            "hours": {"value": 1},
            "minutes": {"value": 2},
            "seconds": {"value": 3},
        },
        device_id=device_id,
    )

    async with asyncio.timeout(1):
        await started_event.wait()

    result = await intent.async_handle(
        hass, "test", intent.INTENT_CANCEL_TIMER, {}, device_id=device_id
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE


async def test_increase_timer(hass: HomeAssistant, init_components) -> None:
    """Test increasing the time of a running timer."""
    device_id = _make_timer_device_id(hass)
    started_event = asyncio.Event()
    updated_event = asyncio.Event()
    cancelled_event = asyncio.Event()

    timer_name = "test timer"
    timer_id: str | None = None
    original_total_seconds = -1

    @callback
    def handle_timer(event: TimerListEvent) -> None:
        nonlocal timer_id, original_total_seconds
        item = event.item

        assert item.duration == timedelta(hours=1, minutes=2, seconds=3)

        if timer_name is not None:
            assert item.name == timer_name

        if event.event_type == TimerListEventType.STARTED:
            timer_id = item.timer_id
            original_total_seconds = int(item.duration.total_seconds())
            started_event.set()
        elif event.event_type == TimerListEventType.UPDATED:
            assert item.timer_id == timer_id

            # Timer was increased. The duration reflects the timer's original
            # length and does not grow past it, only the remaining time does.
            assert _remaining_seconds(item) > original_total_seconds
            assert int(item.duration.total_seconds()) == original_total_seconds
            updated_event.set()
        elif event.event_type == TimerListEventType.CANCELLED:
            assert item.timer_id == timer_id
            cancelled_event.set()

    await _register_timer_device(hass, device_id, handle_timer)

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {
            "name": {"value": timer_name},
            "hours": {"value": 1},
            "minutes": {"value": 2},
            "seconds": {"value": 3},
        },
        device_id=device_id,
    )

    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Adding 0 seconds has no effect
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_INCREASE_TIMER,
        {
            "start_hours": {"value": 1},
            "start_minutes": {"value": 2},
            "start_seconds": {"value": 3},
            "hours": {"value": 0},
            "minutes": {"value": 0},
            "seconds": {"value": 0},
        },
        device_id=device_id,
    )

    assert result.response_type is intent.IntentResponseType.ACTION_DONE
    assert not updated_event.is_set()

    # Add 1 hour, 5 minutes, and 30 seconds to the timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_INCREASE_TIMER,
        {
            "start_hours": {"value": 1},
            "start_minutes": {"value": 2},
            "start_seconds": {"value": 3},
            "hours": {"value": 1},
            "minutes": {"value": 5},
            "seconds": {"value": 30},
        },
        device_id=device_id,
    )

    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await updated_event.wait()

    # Cancel the timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {"name": {"value": timer_name}},
        device_id=device_id,
    )

    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await cancelled_event.wait()


async def test_decrease_timer(hass: HomeAssistant, init_components) -> None:
    """Test decreasing the time of a running timer."""
    device_id = _make_timer_device_id(hass)
    started_event = asyncio.Event()
    updated_event = asyncio.Event()
    cancelled_event = asyncio.Event()

    timer_name = "test timer"
    timer_id: str | None = None
    original_total_seconds = 0

    @callback
    def handle_timer(event: TimerListEvent) -> None:
        nonlocal timer_id, original_total_seconds
        item = event.item

        assert item.duration == timedelta(hours=1, minutes=2, seconds=3)

        if timer_name is not None:
            assert item.name == timer_name

        if event.event_type == TimerListEventType.STARTED:
            timer_id = item.timer_id
            original_total_seconds = int(item.duration.total_seconds())
            started_event.set()
        elif event.event_type == TimerListEventType.UPDATED:
            assert item.timer_id == timer_id

            # Timer was decreased
            assert _remaining_seconds(item) <= (original_total_seconds - 30)
            assert int(item.duration.total_seconds()) == original_total_seconds

            updated_event.set()
        elif event.event_type == TimerListEventType.CANCELLED:
            assert item.timer_id == timer_id
            cancelled_event.set()

    await _register_timer_device(hass, device_id, handle_timer)

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {
            "name": {"value": timer_name},
            "hours": {"value": 1},
            "minutes": {"value": 2},
            "seconds": {"value": 3},
        },
        device_id=device_id,
    )

    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Remove 30 seconds from the timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_DECREASE_TIMER,
        {
            "start_hours": {"value": 1},
            "start_minutes": {"value": 2},
            "start_seconds": {"value": 3},
            "seconds": {"value": 30},
        },
        device_id=device_id,
    )

    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Cancel the timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {"name": {"value": timer_name}},
        device_id=device_id,
    )

    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await cancelled_event.wait()


async def test_decrease_timer_below_zero(hass: HomeAssistant, init_components) -> None:
    """Test decreasing the time of a running timer below 0 seconds.

    Removing more time than remains finishes the timer immediately (see
    LocalTimerListEntity.async_add_time), rather than emitting an
    intermediate "updated" event at 0 seconds.
    """
    started_event = asyncio.Event()
    finished_event = asyncio.Event()

    device_id = _make_timer_device_id(hass)
    timer_id: str | None = None
    original_total_seconds = 0

    @callback
    def handle_timer(event: TimerListEvent) -> None:
        nonlocal timer_id, original_total_seconds
        item = event.item

        assert item.name is None
        assert item.duration == timedelta(hours=1, minutes=2, seconds=3)

        if event.event_type == TimerListEventType.STARTED:
            timer_id = item.timer_id
            original_total_seconds = int(item.duration.total_seconds())
            started_event.set()
        elif event.event_type == TimerListEventType.FINISHED:
            assert item.timer_id == timer_id
            assert _remaining_seconds(item) == 0
            finished_event.set()

    await _register_timer_device(hass, device_id, handle_timer)

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {
            "hours": {"value": 1},
            "minutes": {"value": 2},
            "seconds": {"value": 3},
        },
        device_id=device_id,
    )

    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Remove more time than was on the timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_DECREASE_TIMER,
        {
            "start_hours": {"value": 1},
            "start_minutes": {"value": 2},
            "start_seconds": {"value": 3},
            "seconds": {"value": original_total_seconds + 1},
        },
        device_id=device_id,
    )

    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await asyncio.gather(started_event.wait(), finished_event.wait())


async def test_find_timer_failed(hass: HomeAssistant, init_components) -> None:
    """Test finding a timer with the wrong info."""
    device_id = _make_timer_device_id(hass)

    # No device id
    with pytest.raises(TimersNotSupportedError):
        await intent.async_handle(
            hass,
            "test",
            intent.INTENT_START_TIMER,
            {"minutes": {"value": 5}},
            device_id=None,
        )

    # Unregistered device
    with pytest.raises(TimersNotSupportedError):
        await intent.async_handle(
            hass,
            "test",
            intent.INTENT_START_TIMER,
            {"minutes": {"value": 5}},
            device_id=device_id,
        )

    # The device needs a timer_list entity before we can do anything with timers
    await _register_timer_device(hass, device_id)

    # Start a 5 minute timer for pizza
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "pizza"}, "minutes": {"value": 5}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    # Right name
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_INCREASE_TIMER,
        {"name": {"value": "PIZZA "}, "minutes": {"value": 1}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    # Wrong name
    with pytest.raises(intent.IntentError):
        await intent.async_handle(
            hass,
            "test",
            intent.INTENT_CANCEL_TIMER,
            {"name": {"value": "does-not-exist"}},
            device_id=device_id,
        )

    # Right start time
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_INCREASE_TIMER,
        {"start_minutes": {"value": 5}, "minutes": {"value": 1}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    # Wrong start time
    with pytest.raises(intent.IntentError):
        await intent.async_handle(
            hass,
            "test",
            intent.INTENT_CANCEL_TIMER,
            {"start_minutes": {"value": 1}},
            device_id=device_id,
        )


async def test_timers_are_device_scoped(hass: HomeAssistant, init_components) -> None:
    """Test that a device only sees and controls its own timer_list entity."""
    device_a = _make_timer_device_id(hass)
    device_b = _make_timer_device_id(hass)

    await _register_timer_device(hass, device_a, MagicMock())
    await _register_timer_device(hass, device_b, MagicMock())

    # Start a timer on each device
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "pizza"}, "minutes": {"value": 10}},
        device_id=device_a,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "tv"}, "minutes": {"value": 15}},
        device_id=device_b,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    # Each device only sees its own timer
    for device_id, expected_name in ((device_a, "pizza"), (device_b, "tv")):
        result = await intent.async_handle(
            hass, "test", intent.INTENT_TIMER_STATUS, {}, device_id=device_id
        )
        assert result.response_type is intent.IntentResponseType.ACTION_DONE
        timers = result.speech_slots.get("timers", [])
        assert len(timers) == 1
        assert timers[0].get(ATTR_NAME) == expected_name

    # Device A cannot reach device B's timer, even by its name
    with pytest.raises(TimerNotFoundError):
        await intent.async_handle(
            hass,
            "test",
            intent.INTENT_CANCEL_TIMER,
            {"name": {"value": "tv"}},
            device_id=device_a,
        )

    # Cancelling all of device A's timers leaves device B's timer untouched
    result = await intent.async_handle(
        hass, "test", intent.INTENT_CANCEL_ALL_TIMERS, {}, device_id=device_a
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.speech_slots.get("canceled", 0) == 1

    result = await intent.async_handle(
        hass, "test", intent.INTENT_TIMER_STATUS, {}, device_id=device_b
    )
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 1
    assert timers[0].get(ATTR_NAME) == "tv"

    # A device without a timer_list entity does not support timers
    no_entity_device = _make_timer_device_id(hass)
    with pytest.raises(TimersNotSupportedError):
        await intent.async_handle(
            hass,
            "test",
            intent.INTENT_TIMER_STATUS,
            {},
            device_id=no_entity_device,
        )


async def test_pause_unpause_timer(hass: HomeAssistant, init_components) -> None:
    """Test pausing and unpausing a running timer."""
    device_id = _make_timer_device_id(hass)

    started_event = asyncio.Event()
    updated_event = asyncio.Event()

    expected_active = True

    @callback
    def handle_timer(event: TimerListEvent) -> None:
        if event.event_type == TimerListEventType.STARTED:
            started_event.set()
        elif event.event_type == TimerListEventType.UPDATED:
            assert (event.item.status == TimerStatus.ACTIVE) == expected_active
            updated_event.set()

    await _register_timer_device(hass, device_id, handle_timer)

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"minutes": {"value": 5}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Pause the timer
    expected_active = False
    result = await intent.async_handle(
        hass, "test", intent.INTENT_PAUSE_TIMER, {}, device_id=device_id
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await updated_event.wait()

    # Pausing again will fail because there are no running timers
    with pytest.raises(TimerNotFoundError):
        await intent.async_handle(
            hass, "test", intent.INTENT_PAUSE_TIMER, {}, device_id=device_id
        )

    # Unpause the timer
    updated_event.clear()
    expected_active = True
    result = await intent.async_handle(
        hass, "test", intent.INTENT_UNPAUSE_TIMER, {}, device_id=device_id
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await updated_event.wait()

    # Unpausing again will fail because there are no paused timers
    with pytest.raises(TimerNotFoundError):
        await intent.async_handle(
            hass, "test", intent.INTENT_UNPAUSE_TIMER, {}, device_id=device_id
        )


async def test_pause_unpause_again_is_noop(
    hass: HomeAssistant, init_components
) -> None:
    """Test that pausing/unpausing an already-paused/running timer emits nothing."""
    handle_timer = MagicMock()

    device_id = _make_timer_device_id(hass)
    await _register_timer_device(hass, device_id, handle_timer)
    entity = _get_timer_entity(hass, device_id)

    timer_id = await entity.async_start_timer(name=None, duration=timedelta(minutes=5))
    (timer_item,) = [t for t in entity.timers if t.timer_id == timer_id]
    assert timer_item.status == TimerStatus.ACTIVE

    # Pause
    handle_timer.reset_mock()
    await entity.async_pause_timer(timer_id)
    handle_timer.assert_called_once()

    # Pausing again does not emit an event
    handle_timer.reset_mock()
    await entity.async_pause_timer(timer_id)
    handle_timer.assert_not_called()

    # Unpause
    handle_timer.reset_mock()
    await entity.async_unpause_timer(timer_id)
    handle_timer.assert_called_once()

    # Unpausing again does not emit an event
    handle_timer.reset_mock()
    await entity.async_unpause_timer(timer_id)
    handle_timer.assert_not_called()


async def test_timer_status_with_names(hass: HomeAssistant, init_components) -> None:
    """Test getting the status of named timers."""
    device_id = _make_timer_device_id(hass)

    started_event = asyncio.Event()
    num_started = 0

    @callback
    def handle_timer(event: TimerListEvent) -> None:
        nonlocal num_started

        if event.event_type == TimerListEventType.STARTED:
            num_started += 1
            if num_started == 4:
                started_event.set()

    await _register_timer_device(hass, device_id, handle_timer)

    # Start timers with names
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "pizza"}, "minutes": {"value": 10}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "pizza"}, "minutes": {"value": 15}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "cookies"}, "minutes": {"value": 20}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "chicken"}, "hours": {"value": 2}, "seconds": {"value": 30}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    # Wait for all timers to start
    async with asyncio.timeout(1):
        await started_event.wait()

    # No constraints returns all of the device's timers
    result = await intent.async_handle(
        hass, "test", intent.INTENT_TIMER_STATUS, {}, device_id=device_id
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 4
    assert {t.get(ATTR_NAME) for t in timers} == {"pizza", "cookies", "chicken"}

    # Get status of cookie timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"name": {"value": "cookies"}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 1
    assert timers[0].get(ATTR_NAME) == "cookies"
    assert timers[0].get("start_minutes") == 20

    # Get status of pizza timers
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"name": {"value": "pizza"}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 2
    assert timers[0].get(ATTR_NAME) == "pizza"
    assert timers[1].get(ATTR_NAME) == "pizza"
    assert {timers[0].get("start_minutes"), timers[1].get("start_minutes")} == {10, 15}

    # Get status of one pizza timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"name": {"value": "pizza"}, "start_minutes": {"value": 10}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 1
    assert timers[0].get(ATTR_NAME) == "pizza"
    assert timers[0].get("start_minutes") == 10

    # Get status of one chicken timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {
            "name": {"value": "chicken"},
            "start_hours": {"value": 2},
            "start_seconds": {"value": 30},
        },
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 1
    assert timers[0].get(ATTR_NAME) == "chicken"
    assert timers[0].get("start_hours") == 2
    assert timers[0].get("start_minutes") == 0
    assert timers[0].get("start_seconds") == 30

    # Wrong name results in an empty list
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"name": {"value": "does-not-exist"}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 0

    # Wrong start time results in an empty list
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {
            "start_hours": {"value": 100},
            "start_minutes": {"value": 100},
            "start_seconds": {"value": 100},
        },
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 0


def test_round_time() -> None:
    """Test lower-precision time rounded."""

    # hours
    assert _round_time(1, 10, 30) == (1, 0, 0)
    assert _round_time(1, 48, 30) == (2, 0, 0)
    assert _round_time(2, 25, 30) == (2, 30, 0)

    # minutes
    assert _round_time(0, 1, 10) == (0, 1, 0)
    assert _round_time(0, 1, 48) == (0, 2, 0)
    assert _round_time(0, 2, 25) == (0, 2, 30)

    # seconds
    assert _round_time(0, 0, 6) == (0, 0, 6)
    assert _round_time(0, 0, 15) == (0, 0, 10)
    assert _round_time(0, 0, 58) == (0, 1, 0)
    assert _round_time(0, 0, 25) == (0, 0, 20)
    assert _round_time(0, 0, 35) == (0, 0, 30)


async def test_pause_unpause_timer_disambiguate(
    hass: HomeAssistant, init_components
) -> None:
    """Test disamgibuating timers by their paused state."""
    device_id = _make_timer_device_id(hass)
    started_timer_ids: list[str] = []
    paused_timer_ids: list[str] = []
    unpaused_timer_ids: list[str] = []

    started_event = asyncio.Event()
    updated_event = asyncio.Event()

    @callback
    def handle_timer(event: TimerListEvent) -> None:
        item = event.item
        if event.event_type == TimerListEventType.STARTED:
            started_event.set()
            started_timer_ids.append(item.timer_id)
        elif event.event_type == TimerListEventType.UPDATED:
            updated_event.set()
            if item.status == TimerStatus.ACTIVE:
                unpaused_timer_ids.append(item.timer_id)
            else:
                paused_timer_ids.append(item.timer_id)

    await _register_timer_device(hass, device_id, handle_timer)

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"minutes": {"value": 5}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Pause the timer
    result = await intent.async_handle(
        hass, "test", intent.INTENT_PAUSE_TIMER, {}, device_id=device_id
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await updated_event.wait()

    # Start another timer
    started_event.clear()
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"minutes": {"value": 10}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()
        assert len(started_timer_ids) == 2

    # We can pause the more recent timer without more information because the
    # first one is paused.
    updated_event.clear()
    result = await intent.async_handle(
        hass, "test", intent.INTENT_PAUSE_TIMER, {}, device_id=device_id
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await updated_event.wait()
        assert len(paused_timer_ids) == 2
        assert paused_timer_ids[1] == started_timer_ids[1]

    # We have to explicitly unpause now
    updated_event.clear()
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_UNPAUSE_TIMER,
        {"start_minutes": {"value": 10}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await updated_event.wait()
        assert len(unpaused_timer_ids) == 1
        assert unpaused_timer_ids[0] == started_timer_ids[1]

    # We can resume the older timer without more information because the
    # second one is running.
    updated_event.clear()
    result = await intent.async_handle(
        hass, "test", intent.INTENT_UNPAUSE_TIMER, {}, device_id=device_id
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await updated_event.wait()
        assert len(unpaused_timer_ids) == 2
        assert unpaused_timer_ids[1] == started_timer_ids[0]


async def test_async_device_supports_timers(hass: HomeAssistant) -> None:
    """Test async_device_supports_timers function."""
    device_id = _make_timer_device_id(hass)

    # Before intent initialization
    assert not async_device_supports_timers(hass, device_id)

    # After intent initialization
    assert await async_setup_component(hass, DOMAIN, {})
    assert not async_device_supports_timers(hass, device_id)

    await _register_timer_device(hass, device_id)

    # After the device's timer_list entity is created
    assert async_device_supports_timers(hass, device_id)


async def test_cancel_all_timers(hass: HomeAssistant, init_components) -> None:
    """Test cancelling all timers."""
    device_id = _make_timer_device_id(hass)

    started_event = asyncio.Event()
    num_started = 0

    @callback
    def handle_timer(event: TimerListEvent) -> None:
        nonlocal num_started

        if event.event_type == TimerListEventType.STARTED:
            num_started += 1
            if num_started == 3:
                started_event.set()

    await _register_timer_device(hass, device_id, handle_timer)

    # Start timers
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "pizza"}, "minutes": {"value": 10}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "tv"}, "minutes": {"value": 10}},
        device_id=device_id,
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE

    result2 = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "media"}, "minutes": {"value": 15}},
        device_id=device_id,
    )
    assert result2.response_type is intent.IntentResponseType.ACTION_DONE

    # Wait for all timers to start
    async with asyncio.timeout(1):
        await started_event.wait()

    # Cancel all timers
    result = await intent.async_handle(
        hass, "test", intent.INTENT_CANCEL_ALL_TIMERS, {}, device_id=device_id
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.speech_slots.get("canceled", 0) == 3

    # No timers should be running for test_device
    result = await intent.async_handle(
        hass, "test", intent.INTENT_TIMER_STATUS, {}, device_id=device_id
    )
    assert result.response_type is intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 0
