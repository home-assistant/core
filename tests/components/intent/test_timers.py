"""Tests for intent timers."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.intent.timers import (
    MultipleTimersMatchedError,
    TimerEventType,
    TimerInfo,
    TimerManager,
    TimerNotFoundError,
    TimersNotSupportedError,
    _round_time,
    async_device_supports_timers,
    async_register_timer_handler,
)
from homeassistant.const import ATTR_DEVICE_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, callback
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

    @callback
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

    async_register_timer_handler(hass, device_id, handle_timer)

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

    @callback
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

    async_register_timer_handler(hass, device_id, handle_timer)

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
        device_id=device_id,
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

    @callback
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

    async_register_timer_handler(hass, device_id, handle_timer)

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
        device_id=device_id,
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

    @callback
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

    async_register_timer_handler(hass, device_id, handle_timer)

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
        device_id=device_id,
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await cancelled_event.wait()


async def test_decrease_timer_below_zero(hass: HomeAssistant, init_components) -> None:
    """Test decreasing the time of a running timer below 0 seconds."""
    started_event = asyncio.Event()
    updated_event = asyncio.Event()
    finished_event = asyncio.Event()

    device_id = "test_device"
    timer_id: str | None = None
    original_total_seconds = 0

    @callback
    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        nonlocal timer_id, original_total_seconds

        assert timer.device_id == device_id
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

    async_register_timer_handler(hass, device_id, handle_timer)

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
        device_id=device_id,
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await asyncio.gather(
            started_event.wait(), updated_event.wait(), finished_event.wait()
        )


async def test_find_timer_failed(hass: HomeAssistant, init_components) -> None:
    """Test finding a timer with the wrong info."""
    device_id = "test_device"

    for intent_name in (
        intent.INTENT_START_TIMER,
        intent.INTENT_CANCEL_TIMER,
        intent.INTENT_PAUSE_TIMER,
        intent.INTENT_UNPAUSE_TIMER,
        intent.INTENT_INCREASE_TIMER,
        intent.INTENT_DECREASE_TIMER,
        intent.INTENT_TIMER_STATUS,
    ):
        if intent_name in (
            intent.INTENT_START_TIMER,
            intent.INTENT_INCREASE_TIMER,
            intent.INTENT_DECREASE_TIMER,
        ):
            slots = {"minutes": {"value": 5}}
        else:
            slots = {}

        # No device id
        with pytest.raises(TimersNotSupportedError):
            await intent.async_handle(
                hass,
                "test",
                intent_name,
                slots,
                device_id=None,
            )

        # Unregistered device
        with pytest.raises(TimersNotSupportedError):
            await intent.async_handle(
                hass,
                "test",
                intent_name,
                slots,
                device_id=device_id,
            )

    # Must register a handler before we can do anything with timers
    @callback
    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        pass

    async_register_timer_handler(hass, device_id, handle_timer)

    # Start a 5 minute timer for pizza
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "pizza"}, "minutes": {"value": 5}},
        device_id=device_id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Right name
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_INCREASE_TIMER,
        {"name": {"value": "PIZZA "}, "minutes": {"value": 1}},
        device_id=device_id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

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
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Wrong start time
    with pytest.raises(intent.IntentError):
        await intent.async_handle(
            hass,
            "test",
            intent.INTENT_CANCEL_TIMER,
            {"start_minutes": {"value": 1}},
            device_id=device_id,
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

    cancelled_event = asyncio.Event()
    timer_info: TimerInfo | None = None

    @callback
    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        nonlocal timer_info

        if event_type == TimerEventType.CANCELLED:
            timer_info = timer
            cancelled_event.set()

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

    async_register_timer_handler(hass, device_alice_study.id, handle_timer)
    async_register_timer_handler(hass, device_bob_kitchen_1.id, handle_timer)

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

    # Alice: cancel my timer
    cancelled_event.clear()
    timer_info = None
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

    async_register_timer_handler(hass, device_alice_bedroom.id, handle_timer)
    async_register_timer_handler(hass, device_bob_living_room.id, handle_timer)

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

    # Trying to cancel the remaining two timers from a disconnected area fails
    area_garage = area_registry.async_create("garage")
    device_garage = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("test", "garage")},
    )
    device_registry.async_update_device(device_garage.id, area_id=area_garage.id)
    async_register_timer_handler(hass, device_garage.id, handle_timer)

    with pytest.raises(MultipleTimersMatchedError):
        await intent.async_handle(
            hass,
            "test",
            intent.INTENT_CANCEL_TIMER,
            {},
            device_id=device_garage.id,
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

    async_register_timer_handler(hass, device_bob_kitchen_2.id, handle_timer)

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
    device_id = "test_device"

    started_event = asyncio.Event()
    updated_event = asyncio.Event()

    expected_active = True

    @callback
    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        if event_type == TimerEventType.STARTED:
            started_event.set()
        elif event_type == TimerEventType.UPDATED:
            assert timer.is_active == expected_active
            updated_event.set()

    async_register_timer_handler(hass, device_id, handle_timer)

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"minutes": {"value": 5}},
        device_id=device_id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Pause the timer
    expected_active = False
    result = await intent.async_handle(
        hass, "test", intent.INTENT_PAUSE_TIMER, {}, device_id=device_id
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

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
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await updated_event.wait()

    # Unpausing again will fail because there are no paused timers
    with pytest.raises(TimerNotFoundError):
        await intent.async_handle(
            hass, "test", intent.INTENT_UNPAUSE_TIMER, {}, device_id=device_id
        )


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


async def test_timer_manager_pause_unpause(hass: HomeAssistant) -> None:
    """Test that pausing/unpausing again will not have an affect."""
    timer_manager = TimerManager(hass)

    # Start a timer
    handle_timer = MagicMock()

    device_id = "test_device"
    timer_manager.register_handler(device_id, handle_timer)

    timer_id = timer_manager.start_timer(
        device_id,
        hours=None,
        minutes=5,
        seconds=None,
        language=hass.config.language,
    )

    assert timer_id in timer_manager.timers
    assert timer_manager.timers[timer_id].is_active

    # Pause
    handle_timer.reset_mock()
    timer_manager.pause_timer(timer_id)
    handle_timer.assert_called_once()

    # Pausing again does not call handler
    handle_timer.reset_mock()
    timer_manager.pause_timer(timer_id)
    handle_timer.assert_not_called()

    # Unpause
    handle_timer.reset_mock()
    timer_manager.unpause_timer(timer_id)
    handle_timer.assert_called_once()

    # Unpausing again does not call handler
    handle_timer.reset_mock()
    timer_manager.unpause_timer(timer_id)
    handle_timer.assert_not_called()


async def test_timers_not_supported(hass: HomeAssistant) -> None:
    """Test unregistered device ids raise TimersNotSupportedError."""
    timer_manager = TimerManager(hass)

    with pytest.raises(TimersNotSupportedError):
        timer_manager.start_timer(
            "does-not-exist",
            hours=None,
            minutes=5,
            seconds=None,
            language=hass.config.language,
        )

    # Start a timer
    @callback
    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        pass

    device_id = "test_device"
    unregister = timer_manager.register_handler(device_id, handle_timer)

    timer_id = timer_manager.start_timer(
        device_id,
        hours=None,
        minutes=5,
        seconds=None,
        language=hass.config.language,
    )

    # Unregister handler so device no longer "supports" timers
    unregister()

    # All operations on the timer should not crash
    timer_manager.add_time(timer_id, 1)

    timer_manager.remove_time(timer_id, 1)

    timer_manager.pause_timer(timer_id)

    timer_manager.unpause_timer(timer_id)

    timer_manager.cancel_timer(timer_id)


async def test_timer_status_with_names(hass: HomeAssistant, init_components) -> None:
    """Test getting the status of named timers."""
    device_id = "test_device"

    started_event = asyncio.Event()
    num_started = 0

    @callback
    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        nonlocal num_started

        if event_type == TimerEventType.STARTED:
            num_started += 1
            if num_started == 4:
                started_event.set()

    async_register_timer_handler(hass, device_id, handle_timer)

    # Start timers with names
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "pizza"}, "minutes": {"value": 10}},
        device_id=device_id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "pizza"}, "minutes": {"value": 15}},
        device_id=device_id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "cookies"}, "minutes": {"value": 20}},
        device_id=device_id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"name": {"value": "chicken"}, "hours": {"value": 2}, "seconds": {"value": 30}},
        device_id=device_id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Wait for all timers to start
    async with asyncio.timeout(1):
        await started_event.wait()

    # No constraints returns all timers
    result = await intent.async_handle(
        hass, "test", intent.INTENT_TIMER_STATUS, {}, device_id=device_id
    )
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
        device_id=device_id,
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
        device_id=device_id,
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
        device_id=device_id,
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
        device_id=device_id,
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
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"name": {"value": "does-not-exist"}},
        device_id=device_id,
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
        device_id=device_id,
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

    @callback
    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        nonlocal num_started

        if event_type == TimerEventType.STARTED:
            num_started += 1
            if num_started == num_timers:
                started_event.set()

    async_register_timer_handler(hass, device_kitchen.id, handle_timer)
    async_register_timer_handler(hass, device_living_room.id, handle_timer)

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
    result = await intent.async_handle(
        hass, "test", intent.INTENT_TIMER_STATUS, {}, device_id=device_kitchen.id
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == num_timers
    assert {t.get(ATTR_NAME) for t in timers} == {"pizza", "tv", "media"}

    # Filter by area (target kitchen from living room)
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"area": {"value": "kitchen"}},
        device_id=device_living_room.id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 1
    assert timers[0].get(ATTR_NAME) == "pizza"

    # Filter by area (target living room from kitchen)
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"area": {"value": "living room"}},
        device_id=device_kitchen.id,
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
        device_id=device_kitchen.id,
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
        device_id=device_kitchen.id,
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
        device_id=device_kitchen.id,
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
        device_id=device_living_room.id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Cancel by area
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {"area": {"value": "living room"}},
        device_id=device_living_room.id,
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


async def test_start_timer_with_conversation_command(
    hass: HomeAssistant, init_components
) -> None:
    """Test starting a timer with an conversation command and having it finish."""
    device_id = "test_device"
    timer_name = "test timer"
    test_command = "turn on the lights"
    agent_id = "test_agent"

    mock_handle_timer = MagicMock()
    async_register_timer_handler(hass, device_id, mock_handle_timer)

    timer_manager = TimerManager(hass)
    with pytest.raises(ValueError):
        timer_manager.start_timer(
            device_id=None,
            hours=None,
            minutes=5,
            seconds=None,
            language=hass.config.language,
        )

    with patch("homeassistant.components.conversation.async_converse") as mock_converse:
        result = await intent.async_handle(
            hass,
            "test",
            intent.INTENT_START_TIMER,
            {
                "name": {"value": timer_name},
                "seconds": {"value": 0},
                "conversation_command": {"value": test_command},
            },
            device_id=device_id,
            conversation_agent_id=agent_id,
        )

        assert result.response_type == intent.IntentResponseType.ACTION_DONE

        # No timer events for delayed commands
        mock_handle_timer.assert_not_called()

        # Wait for process service call to finish
        await hass.async_block_till_done()
        mock_converse.assert_called_once()
        assert mock_converse.call_args.args[1] == test_command


async def test_pause_unpause_timer_disambiguate(
    hass: HomeAssistant, init_components
) -> None:
    """Test disamgibuating timers by their paused state."""
    device_id = "test_device"
    started_timer_ids: list[str] = []
    paused_timer_ids: list[str] = []
    unpaused_timer_ids: list[str] = []

    started_event = asyncio.Event()
    updated_event = asyncio.Event()

    @callback
    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        if event_type == TimerEventType.STARTED:
            started_event.set()
            started_timer_ids.append(timer.id)
        elif event_type == TimerEventType.UPDATED:
            updated_event.set()
            if timer.is_active:
                unpaused_timer_ids.append(timer.id)
            else:
                paused_timer_ids.append(timer.id)

    async_register_timer_handler(hass, device_id, handle_timer)

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_START_TIMER,
        {"minutes": {"value": 5}},
        device_id=device_id,
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Pause the timer
    result = await intent.async_handle(
        hass, "test", intent.INTENT_PAUSE_TIMER, {}, device_id=device_id
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

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
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()
        assert len(started_timer_ids) == 2

    # We can pause the more recent timer without more information because the
    # first one is paused.
    updated_event.clear()
    result = await intent.async_handle(
        hass, "test", intent.INTENT_PAUSE_TIMER, {}, device_id=device_id
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

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
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

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
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await updated_event.wait()
        assert len(unpaused_timer_ids) == 2
        assert unpaused_timer_ids[1] == started_timer_ids[0]


async def test_async_device_supports_timers(hass: HomeAssistant) -> None:
    """Test async_device_supports_timers function."""
    device_id = "test_device"

    # Before intent initialization
    assert not async_device_supports_timers(hass, device_id)

    # After intent initialization
    assert await async_setup_component(hass, "intent", {})
    assert not async_device_supports_timers(hass, device_id)

    @callback
    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        pass

    async_register_timer_handler(hass, device_id, handle_timer)

    # After handler registration
    assert async_device_supports_timers(hass, device_id)
