"""Tests for intent timers."""

import asyncio

import pytest

from homeassistant.components.intent.timers import (
    ATTR_DEVICE_ID,
    ATTR_ID,
    ATTR_NAME,
    ATTR_SECONDS_LEFT,
    ATTR_START_HOURS,
    ATTR_START_MINUTES,
    ATTR_START_SECONDS,
    EVENT_INTENT_TIMER_CANCELLED,
    EVENT_INTENT_TIMER_FINISHED,
    EVENT_INTENT_TIMER_STARTED,
    EVENT_INTENT_TIMER_UPDATED,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component


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
