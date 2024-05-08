"""Tests for intent timers."""

import asyncio

from homeassistant.components.intent import (
    TimerEvent,
    TimerEventType,
    async_register_timer_handler,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component


async def test_start_finish_timer(hass: HomeAssistant) -> None:
    """Test starting a timer and having it finish."""
    assert await async_setup_component(hass, "intent", {})

    device_id = "test_device"
    started_event = asyncio.Event()
    finished_event = asyncio.Event()

    async def handler(event: TimerEvent) -> None:
        if event.type == TimerEventType.STARTED:
            started_event.set()
        elif event.type == TimerEventType.FINISHED:
            finished_event.set()

    unregister = async_register_timer_handler(hass, device_id, handler)
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
        {"device_id": {"value": device_id}, "seconds": {"value": 0}},
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await asyncio.gather(started_event.wait(), finished_event.wait())

    unregister()


async def test_cancel_timer(hass: HomeAssistant) -> None:
    """Test cancelling a timer."""
    assert await async_setup_component(hass, "intent", {})

    device_id = "test_device"
    timer_name: str | None = None
    started_event = asyncio.Event()
    cancelled_event = asyncio.Event()

    async def handler(event: TimerEvent) -> None:
        if timer_name:
            assert event.name == timer_name

        if event.type == TimerEventType.STARTED:
            started_event.set()
        elif event.type == TimerEventType.CANCELLED:
            cancelled_event.set()

    unregister = async_register_timer_handler(hass, device_id, handler)

    # Cancel by starting time
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
        {"device_id": {"value": device_id}, "minutes": {"value": 1}},
    )

    async with asyncio.timeout(1):
        await started_event.wait()

    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {"start_minutes": {"value": 1}},
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

    unregister()


async def test_increase_timer(hass: HomeAssistant) -> None:
    """Test increasing the time of a running timer."""
    assert await async_setup_component(hass, "intent", {})

    device_id = "test_device"
    started_event = asyncio.Event()
    updated_event = asyncio.Event()
    cancelled_event = asyncio.Event()

    async def handler(event: TimerEvent) -> None:
        if event.type == TimerEventType.STARTED:
            started_event.set()
        elif event.type == TimerEventType.UPDATED:
            assert event.seconds_left > 60
            updated_event.set()
        elif event.type == TimerEventType.CANCELLED:
            cancelled_event.set()

    unregister = async_register_timer_handler(hass, device_id, handler)
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
        {"device_id": {"value": device_id}, "minutes": {"value": 1}},
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Add 30 seconds to the 1 minute timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_INCREASE_TIMER,
        {
            "device_id": {"value": device_id},
            "start_minutes": {"value": 1},
            "seconds": {"value": 30},
        },
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Cancel the timer by its original start time
    await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {"device_id": {"value": device_id}, "start_minutes": {"value": 1}},
    )

    async with asyncio.timeout(1):
        await cancelled_event.wait()

    unregister()


async def test_decrease_timer(hass: HomeAssistant) -> None:
    """Test decreasing the time of a running timer."""
    assert await async_setup_component(hass, "intent", {})

    device_id = "test_device"
    started_event = asyncio.Event()
    updated_event = asyncio.Event()
    cancelled_event = asyncio.Event()

    async def handler(event: TimerEvent) -> None:
        if event.type == TimerEventType.STARTED:
            started_event.set()
        elif event.type == TimerEventType.UPDATED:
            assert event.seconds_left < 60
            updated_event.set()
        elif event.type == TimerEventType.CANCELLED:
            cancelled_event.set()

    unregister = async_register_timer_handler(hass, device_id, handler)
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
        {"device_id": {"value": device_id}, "minutes": {"value": 1}},
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Remove 30 seconds from the 1 minute timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_DECREASE_TIMER,
        {
            "device_id": {"value": device_id},
            "start_minutes": {"value": 1},
            "seconds": {"value": 30},
        },
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await updated_event.wait()

    # Cancel the timer by its original start time
    await intent.async_handle(
        hass,
        "test",
        intent.INTENT_CANCEL_TIMER,
        {"device_id": {"value": device_id}, "start_minutes": {"value": 1}},
    )

    async with asyncio.timeout(1):
        await cancelled_event.wait()

    unregister()


async def test_decrease_timer_below_zero(hass: HomeAssistant) -> None:
    """Test decreasing the time of a running timer below 0 seconds."""
    assert await async_setup_component(hass, "intent", {})

    device_id = "test_device"
    started_event = asyncio.Event()
    updated_event = asyncio.Event()
    finished_event = asyncio.Event()

    async def handler(event: TimerEvent) -> None:
        if event.type == TimerEventType.STARTED:
            started_event.set()
        elif event.type == TimerEventType.UPDATED:
            assert event.seconds_left == 0
            updated_event.set()
        elif event.type == TimerEventType.FINISHED:
            finished_event.set()

    unregister = async_register_timer_handler(hass, device_id, handler)
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_SET_TIMER,
        {"device_id": {"value": device_id}, "minutes": {"value": 1}},
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await started_event.wait()

    # Remove 5 minutes from the 1 minute timer
    result = await intent.async_handle(
        hass,
        "test",
        intent.INTENT_DECREASE_TIMER,
        {
            "device_id": {"value": device_id},
            "start_minutes": {"value": 1},
            "minutes": {"value": 5},
        },
    )

    assert result.response_type == intent.IntentResponseType.ACTION_DONE

    async with asyncio.timeout(1):
        await asyncio.gather(updated_event.wait(), finished_event.wait())

    unregister()
