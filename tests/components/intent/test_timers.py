"""Tests for intent timers."""

import asyncio
from typing import Any

import pytest

from homeassistant.components.intent.timers import (
    ATTR_DEVICE_ID,
    ATTR_ID,
    ATTR_NAME,
    ATTR_PAUSED,
    ATTR_SECONDS_LEFT,
    ATTR_START_HOURS,
    ATTR_START_MINUTES,
    ATTR_START_SECONDS,
    EVENT_INTENT_TIMER_CANCELLED,
    EVENT_INTENT_TIMER_FINISHED,
    EVENT_INTENT_TIMER_STARTED,
    EVENT_INTENT_TIMER_UPDATED,
    MultipleTimersMatchedError,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    floor_registry as fr,
    intent,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_start_finish_timer(hass: HomeAssistant) -> None:
    """Test starting a timer and having it finish."""
    assert await async_setup_component(hass, "intent", {})

    device_id = "test_device"
    timer_name = "test timer"
    started_event = asyncio.Event()
    finished_event = asyncio.Event()

    timer_id: str | None = None

    async def started_listener(event: Event) -> None:
        nonlocal timer_id
        timer_id = event.data[ATTR_ID]

        assert event.data[ATTR_NAME] == timer_name
        assert event.data[ATTR_DEVICE_ID] == device_id
        assert event.data[ATTR_START_HOURS] == 0
        assert event.data[ATTR_START_MINUTES] == 0
        assert event.data[ATTR_START_SECONDS] == 0
        assert (
            event.data[ATTR_SECONDS_LEFT]
            == (60 * 60 * event.data[ATTR_START_HOURS])
            + (60 * event.data[ATTR_START_MINUTES])
            + event.data[ATTR_START_SECONDS]
        )
        started_event.set()

    async def finished_listener(event: Event) -> None:
        assert event.data[ATTR_ID] == timer_id
        assert event.data[ATTR_NAME] == timer_name
        assert event.data[ATTR_DEVICE_ID] == device_id
        assert event.data[ATTR_START_HOURS] == 0
        assert event.data[ATTR_START_MINUTES] == 0
        assert event.data[ATTR_START_SECONDS] == 0
        assert event.data[ATTR_SECONDS_LEFT] == 0
        finished_event.set()

    hass.bus.async_listen(EVENT_INTENT_TIMER_STARTED, started_listener)
    hass.bus.async_listen(EVENT_INTENT_TIMER_FINISHED, finished_listener)

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
        {
            "name": {"value": timer_name},
            "device_id": {"value": device_id},
            "seconds": {"value": 0},
        },
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await asyncio.gather(started_event.wait(), finished_event.wait())


async def test_cancel_timer(hass: HomeAssistant) -> None:
    """Test cancelling a timer."""
    assert await async_setup_component(hass, "intent", {})

    device_id = "test_device"
    timer_name: str | None = None
    started_event = asyncio.Event()
    cancelled_event = asyncio.Event()

    timer_id: str | None = None

    async def started_listener(event: Event) -> None:
        nonlocal timer_id
        timer_id = event.data[ATTR_ID]

        if timer_name is not None:
            assert event.data[ATTR_NAME] == timer_name

        assert event.data[ATTR_DEVICE_ID] == device_id
        assert event.data[ATTR_START_HOURS] == 1
        assert event.data[ATTR_START_MINUTES] == 2
        assert event.data[ATTR_START_SECONDS] == 3
        assert (
            event.data[ATTR_SECONDS_LEFT]
            == (60 * 60 * event.data[ATTR_START_HOURS])
            + (60 * event.data[ATTR_START_MINUTES])
            + event.data[ATTR_START_SECONDS]
        )
        started_event.set()

    async def cancelled_listener(event: Event) -> None:
        assert event.data[ATTR_ID] == timer_id

        if timer_name is not None:
            assert event.data[ATTR_NAME] == timer_name

        assert event.data[ATTR_DEVICE_ID] == device_id
        assert event.data[ATTR_START_HOURS] == 1
        assert event.data[ATTR_START_MINUTES] == 2
        assert event.data[ATTR_START_SECONDS] == 3
        assert event.data[ATTR_SECONDS_LEFT] > 0
        cancelled_event.set()

    hass.bus.async_listen(EVENT_INTENT_TIMER_STARTED, started_listener)
    hass.bus.async_listen(EVENT_INTENT_TIMER_CANCELLED, cancelled_listener)

    # Cancel by starting time
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
        {
            "device_id": {"value": device_id},
            "hours": {"value": 1},
            "minutes": {"value": 2},
            "seconds": {"value": 3},
        },
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
        intent.INTENT_SET_TIMER,
        {
            "device_id": {"value": device_id},
            "name": {"value": timer_name},
            "hours": {"value": 1},
            "minutes": {"value": 2},
            "seconds": {"value": 3},
        },
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


async def test_increase_timer(hass: HomeAssistant) -> None:
    """Test increasing the time of a running timer."""
    assert await async_setup_component(hass, "intent", {})

    device_id = "test_device"
    started_event = asyncio.Event()
    updated_event = asyncio.Event()
    cancelled_event = asyncio.Event()

    timer_name = "test timer"
    timer_id: str | None = None
    original_total_seconds = 0

    async def started_listener(event: Event) -> None:
        nonlocal timer_id, original_total_seconds
        timer_id = event.data[ATTR_ID]
        original_total_seconds = (
            (60 * 60 * event.data[ATTR_START_HOURS])
            + (60 * event.data[ATTR_START_MINUTES])
            + event.data[ATTR_START_SECONDS]
        )
        started_event.set()

    async def updated_listener(event: Event) -> None:
        assert event.data[ATTR_ID] == timer_id
        assert event.data[ATTR_NAME] == timer_name
        assert event.data[ATTR_DEVICE_ID] == device_id
        assert event.data[ATTR_START_HOURS] == 1
        assert event.data[ATTR_START_MINUTES] == 2
        assert event.data[ATTR_START_SECONDS] == 3
        assert event.data[ATTR_SECONDS_LEFT] > original_total_seconds
        updated_event.set()

    async def cancelled_listener(event: Event) -> None:
        cancelled_event.set()

    hass.bus.async_listen(EVENT_INTENT_TIMER_STARTED, started_listener)
    hass.bus.async_listen(EVENT_INTENT_TIMER_UPDATED, updated_listener)
    hass.bus.async_listen(EVENT_INTENT_TIMER_CANCELLED, cancelled_listener)

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
        {
            "device_id": {"value": device_id},
            "name": {"value": timer_name},
            "hours": {"value": 1},
            "minutes": {"value": 2},
            "seconds": {"value": 3},
        },
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Add 30 seconds to the timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_INCREASE_TIMER,
        {
            "device_id": {"value": device_id},
            "start_hours": {"value": 1},
            "start_minutes": {"value": 2},
            "start_seconds": {"value": 3},
            "seconds": {"value": 30},
        },
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


async def test_decrease_timer(hass: HomeAssistant) -> None:
    """Test decreasing the time of a running timer."""
    assert await async_setup_component(hass, "intent", {})

    device_id = "test_device"
    started_event = asyncio.Event()
    updated_event = asyncio.Event()
    cancelled_event = asyncio.Event()

    timer_name = "test timer"
    timer_id: str | None = None
    original_total_seconds = 0

    async def started_listener(event: Event) -> None:
        nonlocal timer_id, original_total_seconds
        timer_id = event.data[ATTR_ID]
        original_total_seconds = (
            (60 * 60 * event.data[ATTR_START_HOURS])
            + (60 * event.data[ATTR_START_MINUTES])
            + event.data[ATTR_START_SECONDS]
        )
        started_event.set()

    async def updated_listener(event: Event) -> None:
        assert event.data[ATTR_ID] == timer_id
        assert event.data[ATTR_NAME] == timer_name
        assert event.data[ATTR_DEVICE_ID] == device_id
        assert event.data[ATTR_START_HOURS] == 1
        assert event.data[ATTR_START_MINUTES] == 2
        assert event.data[ATTR_START_SECONDS] == 3
        assert event.data[ATTR_SECONDS_LEFT] <= original_total_seconds - 30
        updated_event.set()

    async def cancelled_listener(event: Event) -> None:
        cancelled_event.set()

    hass.bus.async_listen(EVENT_INTENT_TIMER_STARTED, started_listener)
    hass.bus.async_listen(EVENT_INTENT_TIMER_UPDATED, updated_listener)
    hass.bus.async_listen(EVENT_INTENT_TIMER_CANCELLED, cancelled_listener)

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
        {
            "device_id": {"value": device_id},
            "name": {"value": timer_name},
            "hours": {"value": 1},
            "minutes": {"value": 2},
            "seconds": {"value": 3},
        },
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
            "device_id": {"value": device_id},
            "start_hours": {"value": 1},
            "start_minutes": {"value": 2},
            "start_seconds": {"value": 3},
            "seconds": {"value": 30},
        },
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


async def test_decrease_timer_below_zero(hass: HomeAssistant) -> None:
    """Test decreasing the time of a running timer below 0 seconds."""
    assert await async_setup_component(hass, "intent", {})

    started_event = asyncio.Event()
    updated_event = asyncio.Event()
    finished_event = asyncio.Event()

    timer_id: str | None = None
    original_total_seconds = 0

    async def started_listener(event: Event) -> None:
        nonlocal timer_id, original_total_seconds
        timer_id = event.data[ATTR_ID]
        original_total_seconds = (
            (60 * 60 * event.data[ATTR_START_HOURS])
            + (60 * event.data[ATTR_START_MINUTES])
            + event.data[ATTR_START_SECONDS]
        )
        started_event.set()

    async def updated_listener(event: Event) -> None:
        assert event.data[ATTR_ID] == timer_id
        assert event.data[ATTR_SECONDS_LEFT] == 0
        updated_event.set()

    async def finished_listener(event: Event) -> None:
        finished_event.set()

    hass.bus.async_listen(EVENT_INTENT_TIMER_STARTED, started_listener)
    hass.bus.async_listen(EVENT_INTENT_TIMER_UPDATED, updated_listener)
    hass.bus.async_listen(EVENT_INTENT_TIMER_FINISHED, finished_listener)

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
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


async def test_find_timer_failed(hass: HomeAssistant) -> None:
    """Test finding a timer with the wrong info."""
    assert await async_setup_component(hass, "intent", {})

    # Start a 5 minute timer for pizza
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
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
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test finding a timer by disambiguating with area/floor."""
    assert await async_setup_component(hass, "intent", {})

    entry = MockConfigEntry()
    entry.add_to_hass(hass)

    # Alice is upstairs in the study
    floor_upstairs = floor_registry.async_create("upstairs")
    area_study = area_registry.async_create("study")
    area_study = area_registry.async_update(
        area_study.id, floor_id=floor_upstairs.floor_id
    )
    device_alice = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("test", "alice")},
    )
    device_registry.async_update_device(device_alice.id, area_id=area_study.id)

    # Bob is downstairs in the kitchen
    floor_downstairs = floor_registry.async_create("downstairs")
    area_kitchen = area_registry.async_create("kitchen")
    area_kitchen = area_registry.async_update(
        area_kitchen.id, floor_id=floor_downstairs.floor_id
    )
    device_bob = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("test", "bob")},
    )
    device_registry.async_update_device(device_bob.id, area_id=area_kitchen.id)

    # Alice: set a 3 minute timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
        {"device_id": {"value": device_alice.id}, "minutes": {"value": 3}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Bob: set a 3 minute timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
        {"device_id": {"value": device_bob.id}, "minutes": {"value": 3}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Alice should hear her timer listed first
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"device_id": {"value": device_alice.id}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 2
    assert timers[0].get(ATTR_DEVICE_ID) == device_alice.id
    assert timers[1].get(ATTR_DEVICE_ID) == device_bob.id

    # Bob should hear his timer listed first
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"device_id": {"value": device_bob.id}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 2
    assert timers[0].get(ATTR_DEVICE_ID) == device_bob.id
    assert timers[1].get(ATTR_DEVICE_ID) == device_alice.id

    # Listen for timer cancellation
    cancelled_event = asyncio.Event()
    cancelled_data: dict[str, Any] = {}

    async def cancelled_listener(event: Event) -> None:
        cancelled_data.update(event.data)
        cancelled_event.set()

    hass.bus.async_listen(EVENT_INTENT_TIMER_CANCELLED, cancelled_listener)

    # Alice: cancel my timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {"device_id": {"value": device_alice.id}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await cancelled_event.wait()

    # Verify this is the 3 minute timer from Alice
    assert cancelled_data.get(ATTR_DEVICE_ID) == device_alice.id
    assert cancelled_data.get(ATTR_START_MINUTES) == 3

    # Cancel Bob's timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {"device_id": {"value": device_bob.id}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Add two new devices in two new areas, one upstairs and one downstairs
    area_bedroom = area_registry.async_create("bedroom")
    area_bedroom = area_registry.async_update(
        area_bedroom.id, floor_id=floor_upstairs.floor_id
    )
    device_alice_2 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("test", "alice-2")},
    )
    device_registry.async_update_device(device_alice_2.id, area_id=area_bedroom.id)

    area_living_room = area_registry.async_create("living_room")
    area_living_room = area_registry.async_update(
        area_living_room.id, floor_id=floor_downstairs.floor_id
    )
    device_bob_2 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("test", "bob-2")},
    )
    device_registry.async_update_device(device_bob_2.id, area_id=area_living_room.id)

    # Alice: set a 3 minute timer (study)
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
        {"device_id": {"value": device_alice.id}, "minutes": {"value": 3}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Alice: set a 3 minute timer (bedroom)
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
        {"device_id": {"value": device_alice_2.id}, "minutes": {"value": 3}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Bob: set a 3 minute timer (kitchen)
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
        {"device_id": {"value": device_bob.id}, "minutes": {"value": 3}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Alice should hear the timer in her area first, then on her floor, then
    # elsewhere.
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_TIMER_STATUS,
        {"device_id": {"value": device_alice.id}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE
    timers = result.speech_slots.get("timers", [])
    assert len(timers) == 3
    assert timers[0].get(ATTR_DEVICE_ID) == device_alice.id
    assert timers[1].get(ATTR_DEVICE_ID) == device_alice_2.id
    assert timers[2].get(ATTR_DEVICE_ID) == device_bob.id

    # Alice cancels the study timer from study
    cancelled_event.clear()
    cancelled_data.clear()
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {"device_id": {"value": device_alice.id}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Verify this is the 3 minute timer from Alice in the study
    assert cancelled_data.get(ATTR_DEVICE_ID) == device_alice.id
    assert cancelled_data.get(ATTR_START_MINUTES) == 3

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
    cancelled_data.clear()
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {"device_id": {"value": device_alice.id}},
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    # Verify this is the 3 minute timer from Alice in the bedroom
    assert cancelled_data.get(ATTR_DEVICE_ID) == device_alice_2.id
    assert cancelled_data.get(ATTR_START_MINUTES) == 3


async def test_pause_unpause_timer(hass: HomeAssistant) -> None:
    """Test pausing and unpausing a running timer."""
    assert await async_setup_component(hass, "intent", {})

    started_event = asyncio.Event()
    updated_event = asyncio.Event()

    expected_paused = False

    async def started_listener(event: Event) -> None:
        started_event.set()

    async def updated_listener(event: Event) -> None:
        assert event.data[ATTR_PAUSED] == expected_paused
        updated_event.set()

    hass.bus.async_listen(EVENT_INTENT_TIMER_STARTED, started_listener)
    hass.bus.async_listen(EVENT_INTENT_TIMER_UPDATED, updated_listener)

    result = await intent.async_handle(
        hass, "test", intent.INTENT_SET_TIMER, {"minutes": {"value": 5}}
    )
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Pause the timer
    expected_paused = True
    result = await intent.async_handle(hass, "test", intent.INTENT_PAUSE_TIMER, {})
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await updated_event.wait()

    # Unpause the timer
    updated_event.clear()
    expected_paused = False
    result = await intent.async_handle(hass, "test", intent.INTENT_UNPAUSE_TIMER, {})
    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await updated_event.wait()
