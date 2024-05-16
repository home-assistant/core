"""Tests for intent timers."""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components.intent.timers import (
    MultipleTimersMatchedError,
    TimerEventType,
    TimerInfo,
    TimerManager,
    TimerNotFoundError,
    _round_time,
    async_register_timer_handler,
)
from homeassistant.const import ATTR_DEVICE_ID, ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    floor_registry as fr,
    intent,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
async def init_components(hass: HomeAssistant) -> None:
    """Initialize required components for tests."""
    assert await async_setup_component(hass, "intent", {})


async def test_start_finish_timer(hass: HomeAssistant, init_components) -> None:
    """Test starting a timer and having it finish."""
    device_id = "test_device"
    timer_name = "test timer"
    started_event = asyncio.Event()
    finished_event = asyncio.Event()

    timer_id: str | None = None

    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        nonlocal timer_id

        assert timer.name == timer_name
        assert timer.device_id == device_id
        assert timer.start_hours is None
        assert timer.start_minutes is None
        assert timer.start_seconds == 0
        assert timer.seconds_left == 0

        if event_type == TimerEventType.STARTED:
            timer_id = timer.id
            started_event.set()
        elif event_type == TimerEventType.FINISHED:
            assert timer.id == timer_id
            finished_event.set()

    async_register_timer_handler(hass, handle_timer)

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

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await asyncio.gather(started_event.wait(), finished_event.wait())


async def test_cancel_timer(hass: HomeAssistant, init_components) -> None:
    """Test cancelling a timer."""
    device_id = "test_device"
    timer_name: str | None = None
    started_event = asyncio.Event()
    cancelled_event = asyncio.Event()

    timer_id: str | None = None

    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        nonlocal timer_id

        assert timer.device_id == device_id
        assert timer.start_hours == 1
        assert timer.start_minutes == 2
        assert timer.start_seconds == 3

        if timer_name is not None:
            assert timer.name == timer_name

        if event_type == TimerEventType.STARTED:
            timer_id = timer.id
            assert (
                timer.seconds_left
                == (60 * 60 * timer.start_hours)
                + (60 * timer.start_minutes)
                + timer.start_seconds
            )
            started_event.set()
        elif event_type == TimerEventType.CANCELLED:
            assert timer.id == timer_id
            assert timer.seconds_left == 0
            cancelled_event.set()

    async_register_timer_handler(hass, handle_timer)

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
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

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
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await cancelled_event.wait()


async def test_increase_timer(hass: HomeAssistant, init_components) -> None:
    """Test increasing the time of a running timer."""
    device_id = "test_device"
    started_event = asyncio.Event()
    updated_event = asyncio.Event()
    cancelled_event = asyncio.Event()

    timer_name = "test timer"
    timer_id: str | None = None
    original_total_seconds = -1

    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        nonlocal timer_id, original_total_seconds

        assert timer.device_id == device_id
        assert timer.start_hours == 1
        assert timer.start_minutes == 2
        assert timer.start_seconds == 3

        if timer_name is not None:
            assert timer.name == timer_name

        if event_type == TimerEventType.STARTED:
            timer_id = timer.id
            original_total_seconds = (
                (60 * 60 * timer.start_hours)
                + (60 * timer.start_minutes)
                + timer.start_seconds
            )
            started_event.set()
        elif event_type == TimerEventType.UPDATED:
            assert timer.id == timer_id

            # Timer was increased
            assert timer.seconds_left > original_total_seconds
            updated_event.set()
        elif event_type == TimerEventType.CANCELLED:
            assert timer.id == timer_id
            cancelled_event.set()

    async_register_timer_handler(hass, handle_timer)

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

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

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

    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    assert not updated_event.is_set()

    # Add 30 seconds to the timer
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

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await updated_event.wait()

    # Cancel the timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {"name": {"value": timer_name}},
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await cancelled_event.wait()


async def test_decrease_timer(hass: HomeAssistant, init_components) -> None:
    """Test decreasing the time of a running timer."""
    device_id = "test_device"
    started_event = asyncio.Event()
    updated_event = asyncio.Event()
    cancelled_event = asyncio.Event()

    timer_name = "test timer"
    timer_id: str | None = None
    original_total_seconds = 0

    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        nonlocal timer_id, original_total_seconds

        assert timer.device_id == device_id
        assert timer.start_hours == 1
        assert timer.start_minutes == 2
        assert timer.start_seconds == 3

        if timer_name is not None:
            assert timer.name == timer_name

        if event_type == TimerEventType.STARTED:
            timer_id = timer.id
            original_total_seconds = (
                (60 * 60 * timer.start_hours)
                + (60 * timer.start_minutes)
                + timer.start_seconds
            )
            started_event.set()
        elif event_type == TimerEventType.UPDATED:
            assert timer.id == timer_id

            # Timer was decreased
            assert timer.seconds_left <= (original_total_seconds - 30)

            updated_event.set()
        elif event_type == TimerEventType.CANCELLED:
            assert timer.id == timer_id
            cancelled_event.set()

    async_register_timer_handler(hass, handle_timer)

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

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

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

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Cancel the timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {"name": {"value": timer_name}},
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await cancelled_event.wait()


async def test_decrease_timer_below_zero(hass: HomeAssistant, init_components) -> None:
    """Test decreasing the time of a running timer below 0 seconds."""
    started_event = asyncio.Event()
    updated_event = asyncio.Event()
    finished_event = asyncio.Event()

    timer_id: str | None = None
    original_total_seconds = 0

    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        nonlocal timer_id, original_total_seconds

        assert timer.device_id is None
        assert timer.name is None
        assert timer.start_hours == 1
        assert timer.start_minutes == 2
        assert timer.start_seconds == 3

        if event_type == TimerEventType.STARTED:
            timer_id = timer.id
            original_total_seconds = (
                (60 * 60 * timer.start_hours)
                + (60 * timer.start_minutes)
                + timer.start_seconds
            )
            started_event.set()
        elif event_type == TimerEventType.UPDATED:
            assert timer.id == timer_id

            # Timer was decreased below zero
            assert timer.seconds_left == 0

            updated_event.set()
        elif event_type == TimerEventType.FINISHED:
            assert timer.id == timer_id
            finished_event.set()

    async_register_timer_handler(hass, handle_timer)

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {
            "hours": {"value": 1},
            "minutes": {"value": 2},
            "seconds": {"value": 3},
        },
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

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
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await asyncio.gather(
            started_event.wait(), updated_event.wait(), finished_event.wait()
        )


async def test_find_timer_failed(hass: HomeAssistant, init_components) -> None:
    """Test finding a timer with the wrong info."""
    # Start a 5 minute timer for pizza
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "pizza"}, "minutes": {"value": 5}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Right name
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_INCREASE_TIMER,
        {"name": {"value": "PIZZA "}, "minutes": {"value": 1}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Wrong name
    with pytest.raises(intent.IntentError):
        await intent.async_handle(
            hass,
            "test",
            intent.INTENT_CANCEL_TIMER,
            {"name": {"value": "does-not-exist"}},
        )

    # Right start time
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_INCREASE_TIMER,
        {"start_minutes": {"value": 5}, "minutes": {"value": 1}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Wrong start time
    with pytest.raises(intent.IntentError):
        await intent.async_handle(
            hass,
            "test",
            intent.INTENT_CANCEL_TIMER,
            {"start_minutes": {"value": 1}},
        )


async def test_disambiguation(
    hass: HomeAssistant,
    init_components,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test finding a timer by disambiguating with area/floor."""
    entry = MockConfigEntry()
    entry.add_to_hass(hass)

    # Alice is upstairs in the study
    floor_upstairs = floor_registry.async_create("upstairs")
    area_study = area_registry.async_create("study")
    area_study = area_registry.async_update(
        area_study.id, floor_id=floor_upstairs.floor_id
    )
    device_alice_study = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("test", "alice")},
    )
    device_registry.async_update_device(device_alice_study.id, area_id=area_study.id)

    # Bob is downstairs in the kitchen
    floor_downstairs = floor_registry.async_create("downstairs")
    area_kitchen = area_registry.async_create("kitchen")
    area_kitchen = area_registry.async_update(
        area_kitchen.id, floor_id=floor_downstairs.floor_id
    )
    device_bob_kitchen_1 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("test", "bob")},
    )
    device_registry.async_update_device(
        device_bob_kitchen_1.id, area_id=area_kitchen.id
    )

    # Alice: set a 3 minute timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"minutes": {"value": 3}},
        device_id=device_alice_study.id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Bob: set a 3 minute timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"minutes": {"value": 3}},
        device_id=device_bob_kitchen_1.id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Alice should hear her timer listed first
    result = await intent.async_handle(
        hass, "test", intent.INTENT_TIMER_STATUS, {}, device_id=device_alice_study.id
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 2
    assert timers[0].get(ATTR_DEVICE_ID) == device_alice_study.id
    assert timers[1].get(ATTR_DEVICE_ID) == device_bob_kitchen_1.id

    # Bob should hear his timer listed first
    result = await intent.async_handle(
        hass, "test", intent.INTENT_TIMER_STATUS, {}, device_id=device_bob_kitchen_1.id
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 2
    assert timers[0].get(ATTR_DEVICE_ID) == device_bob_kitchen_1.id
    assert timers[1].get(ATTR_DEVICE_ID) == device_alice_study.id

    # Listen for timer cancellation
    cancelled_event = asyncio.Event()
    timer_info: TimerInfo | None = None

    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        nonlocal timer_info

        if event_type == TimerEventType.CANCELLED:
            timer_info = timer
            cancelled_event.set()

    async_register_timer_handler(hass, handle_timer)

    # Alice: cancel my timer
    result = await intent.async_handle(
        hass, "test", intent.INTENT_CANCEL_TIMER, {}, device_id=device_alice_study.id
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await cancelled_event.wait()

    # Verify this is the 3 minute timer from Alice
    assert timer_info is not None
    assert timer_info.device_id == device_alice_study.id
    assert timer_info.start_minutes == 3

    # Cancel Bob's timer
    result = await intent.async_handle(
        hass, "test", intent.INTENT_CANCEL_TIMER, {}, device_id=device_bob_kitchen_1.id
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Add two new devices in two new areas, one upstairs and one downstairs
    area_bedroom = area_registry.async_create("bedroom")
    area_bedroom = area_registry.async_update(
        area_bedroom.id, floor_id=floor_upstairs.floor_id
    )
    device_alice_bedroom = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("test", "alice-2")},
    )
    device_registry.async_update_device(
        device_alice_bedroom.id, area_id=area_bedroom.id
    )

    area_living_room = area_registry.async_create("living_room")
    area_living_room = area_registry.async_update(
        area_living_room.id, floor_id=floor_downstairs.floor_id
    )
    device_bob_living_room = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("test", "bob-2")},
    )
    device_registry.async_update_device(
        device_bob_living_room.id, area_id=area_living_room.id
    )

    # Alice: set a 3 minute timer (study)
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"minutes": {"value": 3}},
        device_id=device_alice_study.id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Alice: set a 3 minute timer (bedroom)
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"minutes": {"value": 3}},
        device_id=device_alice_bedroom.id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Bob: set a 3 minute timer (kitchen)
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"minutes": {"value": 3}},
        device_id=device_bob_kitchen_1.id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Bob: set a 3 minute timer (living room)
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"minutes": {"value": 3}},
        device_id=device_bob_living_room.id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Alice should hear the timer in her area first, then on her floor, then
    # elsewhere.
    result = await intent.async_handle(
        hass, "test", intent.INTENT_TIMER_STATUS, {}, device_id=device_alice_study.id
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 4
    assert timers[0].get(ATTR_DEVICE_ID) == device_alice_study.id
    assert timers[1].get(ATTR_DEVICE_ID) == device_alice_bedroom.id
    assert timers[2].get(ATTR_DEVICE_ID) == device_bob_kitchen_1.id
    assert timers[3].get(ATTR_DEVICE_ID) == device_bob_living_room.id

    # Alice cancels the study timer from study
    cancelled_event.clear()
    timer_info = None
    result = await intent.async_handle(
        hass, "test", intent.INTENT_CANCEL_TIMER, {}, device_id=device_alice_study.id
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await cancelled_event.wait()

    # Verify this is the 3 minute timer from Alice in the study
    assert timer_info is not None
    assert timer_info.device_id == device_alice_study.id
    assert timer_info.start_minutes == 3

    # Trying to cancel the remaining two timers without area/floor info fails
    with pytest.raises(MultipleTimersMatchedError):
        await intent.async_handle(
            hass,
            "test",
            intent.INTENT_CANCEL_TIMER,
            {},
        )

    # Alice cancels the bedroom timer from study (same floor)
    cancelled_event.clear()
    timer_info = None
    result = await intent.async_handle(
        hass, "test", intent.INTENT_CANCEL_TIMER, {}, device_id=device_alice_study.id
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await cancelled_event.wait()

    # Verify this is the 3 minute timer from Alice in the bedroom
    assert timer_info is not None
    assert timer_info.device_id == device_alice_bedroom.id
    assert timer_info.start_minutes == 3

    # Add a second device in the kitchen
    device_bob_kitchen_2 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("test", "bob-3")},
    )
    device_registry.async_update_device(
        device_bob_kitchen_2.id, area_id=area_kitchen.id
    )

    # Bob cancels the kitchen timer from a different device
    cancelled_event.clear()
    timer_info = None
    result = await intent.async_handle(
        hass, "test", intent.INTENT_CANCEL_TIMER, {}, device_id=device_bob_kitchen_2.id
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await cancelled_event.wait()

    assert timer_info is not None
    assert timer_info.device_id == device_bob_kitchen_1.id
    assert timer_info.start_minutes == 3

    # Bob cancels the living room timer from the kitchen
    cancelled_event.clear()
    timer_info = None
    result = await intent.async_handle(
        hass, "test", intent.INTENT_CANCEL_TIMER, {}, device_id=device_bob_kitchen_2.id
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await cancelled_event.wait()

    assert timer_info is not None
    assert timer_info.device_id == device_bob_living_room.id
    assert timer_info.start_minutes == 3


async def test_pause_unpause_timer(hass: HomeAssistant, init_components) -> None:
    """Test pausing and unpausing a running timer."""
    started_event = asyncio.Event()
    updated_event = asyncio.Event()

    expected_active = True

    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        if event_type == TimerEventType.STARTED:
            started_event.set()
        elif event_type == TimerEventType.UPDATED:
            assert timer.is_active == expected_active
            updated_event.set()

    async_register_timer_handler(hass, handle_timer)

    result = await intent.async_handle(
        hass, "test", intent.INTENT_START_TIMER, {"minutes": {"value": 5}}
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Pause the timer
    expected_active = False
    result = await intent.async_handle(hass, "test", intent.INTENT_PAUSE_TIMER, {})
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await updated_event.wait()

    # Pausing again will not fire the event
    updated_event.clear()
    result = await intent.async_handle(hass, "test", intent.INTENT_PAUSE_TIMER, {})
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    assert not updated_event.is_set()

    # Unpause the timer
    updated_event.clear()
    expected_active = True
    result = await intent.async_handle(hass, "test", intent.INTENT_UNPAUSE_TIMER, {})
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await updated_event.wait()

    # Unpausing again will not fire the event
    updated_event.clear()
    result = await intent.async_handle(hass, "test", intent.INTENT_UNPAUSE_TIMER, {})
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    assert not updated_event.is_set()


async def test_timer_not_found(hass: HomeAssistant) -> None:
    """Test invalid timer ids raise TimerNotFoundError."""
    timer_manager = TimerManager(hass)

    with pytest.raises(TimerNotFoundError):
        timer_manager.cancel_timer("does-not-exist")

    with pytest.raises(TimerNotFoundError):
        timer_manager.add_time("does-not-exist", 1)

    with pytest.raises(TimerNotFoundError):
        timer_manager.remove_time("does-not-exist", 1)

    with pytest.raises(TimerNotFoundError):
        timer_manager.pause_timer("does-not-exist")

    with pytest.raises(TimerNotFoundError):
        timer_manager.unpause_timer("does-not-exist")


async def test_timer_status_with_names(hass: HomeAssistant, init_components) -> None:
    """Test getting the status of named timers."""
    started_event = asyncio.Event()
    num_started = 0

    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        nonlocal num_started

        if event_type == TimerEventType.STARTED:
            num_started += 1
            if num_started == 4:
                started_event.set()

    async_register_timer_handler(hass, handle_timer)

    # Start timers with names
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "pizza"}, "minutes": {"value": 10}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "pizza"}, "minutes": {"value": 15}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "cookies"}, "minutes": {"value": 20}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "chicken"}, "hours": {"value": 2}, "seconds": {"value": 30}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Wait for all timers to start
    async with asyncio.timeout(1):
        await started_event.wait()

    # No constraints returns all timers
    result = await intent.async_handle(hass, "test", intent.INTENT_TIMER_STATUS, {})
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 4
    assert {t.get(ATTR_NAME) for t in timers} == {"pizza", "cookies", "chicken"}

    # Get status of cookie timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"name": {"value": "cookies"}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
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
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
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
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
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
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 1
    assert timers[0].get(ATTR_NAME) == "chicken"
    assert timers[0].get("start_hours") == 2
    assert timers[0].get("start_minutes") == 0
    assert timers[0].get("start_seconds") == 30

    # Wrong name results in an empty list
    result = await intent.async_handle(
        hass, "test", intent.INTENT_TIMER_STATUS, {"name": {"value": "does-not-exist"}}
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
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
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 0


async def test_area_filter(
    hass: HomeAssistant,
    init_components,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test targeting timers by area name."""
    entry = MockConfigEntry()
    entry.add_to_hass(hass)

    area_kitchen = area_registry.async_create("kitchen")
    device_kitchen = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("test", "kitchen-device")},
    )
    device_registry.async_update_device(device_kitchen.id, area_id=area_kitchen.id)

    area_living_room = area_registry.async_create("living room")
    device_living_room = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("test", "living_room-device")},
    )
    device_registry.async_update_device(
        device_living_room.id, area_id=area_living_room.id
    )

    started_event = asyncio.Event()
    num_timers = 3
    num_started = 0

    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        nonlocal num_started

        if event_type == TimerEventType.STARTED:
            num_started += 1
            if num_started == num_timers:
                started_event.set()

    async_register_timer_handler(hass, handle_timer)

    # Start timers in different areas
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "pizza"}, "minutes": {"value": 10}},
        device_id=device_kitchen.id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "tv"}, "minutes": {"value": 10}},
        device_id=device_living_room.id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "media"}, "minutes": {"value": 15}},
        device_id=device_living_room.id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Wait for all timers to start
    async with asyncio.timeout(1):
        await started_event.wait()

    # No constraints returns all timers
    result = await intent.async_handle(hass, "test", intent.INTENT_TIMER_STATUS, {})
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == num_timers
    assert {t.get(ATTR_NAME) for t in timers} == {"pizza", "tv", "media"}

    # Filter by area (kitchen)
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"area": {"value": "kitchen"}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 1
    assert timers[0].get(ATTR_NAME) == "pizza"

    # Filter by area (living room)
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"area": {"value": "living room"}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 2
    assert {t.get(ATTR_NAME) for t in timers} == {"tv", "media"}

    # Filter by area + name
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"area": {"value": "living room"}, "name": {"value": "tv"}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 1
    assert timers[0].get(ATTR_NAME) == "tv"

    # Filter by area + time
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"area": {"value": "living room"}, "start_minutes": {"value": 15}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 1
    assert timers[0].get(ATTR_NAME) == "media"

    # Filter by area that doesn't exist
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"area": {"value": "does-not-exist"}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 0

    # Cancel by area + time
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {"area": {"value": "living room"}, "start_minutes": {"value": 15}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Cancel by area
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {"area": {"value": "living room"}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Get status with device missing
    with patch(
        "homeassistant.helpers.device_registry.DeviceRegistry.async_get",
        return_value=None,
    ):
        result = await intent.async_handle(
            hass,
            "test",
            intent.INTENT_TIMER_STATUS,
            device_id=device_kitchen.id,
        )
        assert result.response_type == intent.IntentResponseType.ACTION_DONE
        timers = result.speech_slots.get("timers", [])
        assert len(timers) == 1

    # Get status with area missing
    with patch(
        "homeassistant.helpers.area_registry.AreaRegistry.async_get_area",
        return_value=None,
    ):
        result = await intent.async_handle(
            hass,
            "test",
            intent.INTENT_TIMER_STATUS,
            device_id=device_kitchen.id,
        )
        assert result.response_type == intent.IntentResponseType.ACTION_DONE
        timers = result.speech_slots.get("timers", [])
        assert len(timers) == 1


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
