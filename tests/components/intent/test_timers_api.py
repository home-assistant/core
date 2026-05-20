"""Tests for intent timers API."""

import asyncio
from typing import Any

import pytest

from homeassistant.components.intent.timers import (
    EVENT_TIMER_FINISHED,
    TimerEventType,
    TimerInfo,
    async_register_timer_handler,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator

TIMESTAMP = 1735711690.0  # 2025-01-01 06:08:10


@pytest.fixture
async def init_components(hass: HomeAssistant) -> None:
    """Initialize required components for tests."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "intent", {})


@pytest.mark.freeze_time("2025-01-01 06:08:10")
async def test_subscribe_timers_websocket(
    hass: HomeAssistant, init_components, hass_ws_client: WebSocketGenerator
) -> None:
    """Test subscribing to timer updates via websocket."""
    device_id = "test_device"

    timer_id: str | None = None

    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        nonlocal timer_id
        if event_type == TimerEventType.STARTED:
            timer_id = timer.id

    async_register_timer_handler(hass, device_id, handle_timer)

    sub_client = await hass_ws_client(hass)
    control_client = await hass_ws_client(hass)

    await sub_client.send_json_auto_id({"type": "intent/timers/subscribe"})
    msg = await sub_client.receive_json()
    assert msg["success"]
    assert msg["result"]["timers"] == []  # no timers yet

    # Start a timer
    await control_client.send_json_auto_id(
        {
            "type": "intent/timers/start",
            "device_id": device_id,
            "minutes": 30,
            "name": "pizza",
            "finished_event_data": {"test_key": "test_value"},
        }
    )
    msg = await control_client.receive_json()
    assert msg["success"]

    # Verify started event
    msg = await sub_client.receive_json()
    assert msg["event"]["event_type"] == "started"
    assert msg["event"]["timer"] == {
        "id": timer_id,
        "name": "pizza",
        "seconds": 30 * 60,  # 30 minutes
        "device_id": device_id,
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "is_active": True,
        "has_conversation_command": False,
    }

    # Check status
    await control_client.send_json_auto_id({"type": "intent/timers/status"})
    msg = await control_client.receive_json()
    assert msg["success"]
    timers = msg["result"]["timers"]
    assert len(timers) == 1
    timer = timers[0]
    assert timer["id"] == timer_id
    assert timer["name"] == "pizza"
    assert timer["is_active"]
    assert timer["start_hours"] == 0
    assert timer["start_minutes"] == 30
    assert timer["start_seconds"] == 0
    assert timer["total_seconds_left"] > 29 * 60  # 29 minutes
    for key in (
        "hours_left",
        "minutes_left",
        "seconds_left",
        "rounded_hours_left",
        "rounded_minutes_left",
        "rounded_seconds_left",
    ):
        assert key in timer
        assert isinstance(timer[key], int)

    # -----
    # Pause
    # -----
    await control_client.send_json_auto_id(
        {"type": "intent/timers/pause", "timer_id": timer_id}
    )
    msg = await control_client.receive_json()
    assert msg["success"]

    # updated event
    msg = await sub_client.receive_json()
    assert msg["event"]["event_type"] == "updated"
    assert msg["event"]["timer"]["id"] == timer_id
    assert not msg["event"]["timer"]["is_active"]

    # status
    await control_client.send_json_auto_id({"type": "intent/timers/status"})
    msg = await control_client.receive_json()
    assert msg["success"]
    assert msg["result"]["timers"][0]["id"] == timer_id
    assert not msg["result"]["timers"][0]["is_active"]

    # --------
    # Increase
    # --------
    await control_client.send_json_auto_id(
        {"type": "intent/timers/increase", "timer_id": timer_id, "hours": 1}
    )
    msg = await control_client.receive_json()
    assert msg["success"]

    # updated event
    msg = await sub_client.receive_json()
    assert msg["event"]["event_type"] == "updated"
    assert msg["event"]["timer"]["id"] == timer_id
    assert msg["event"]["timer"]["seconds"] == (30 + 60) * 60  # 1.5 hours

    # status
    await control_client.send_json_auto_id({"type": "intent/timers/status"})
    msg = await control_client.receive_json()
    assert msg["success"]
    assert msg["result"]["timers"][0]["id"] == timer_id
    assert msg["result"]["timers"][0]["hours_left"] == 1

    # -------
    # Unpause
    # -------
    await control_client.send_json_auto_id(
        {"type": "intent/timers/unpause", "timer_id": timer_id}
    )
    msg = await control_client.receive_json()
    assert msg["success"]

    # updated event
    msg = await sub_client.receive_json()
    assert msg["event"]["event_type"] == "updated"
    assert msg["event"]["timer"]["id"] == timer_id
    assert msg["event"]["timer"]["is_active"]

    # status
    await control_client.send_json_auto_id({"type": "intent/timers/status"})
    msg = await control_client.receive_json()
    assert msg["success"]
    assert msg["result"]["timers"][0]["id"] == timer_id
    assert msg["result"]["timers"][0]["is_active"]

    timer_finished: dict[str, Any] | None = None
    timer_finished_ready = asyncio.Event()

    # Subscribe to timer finished event before we remove all its time
    @callback
    def handle_finished(event):
        nonlocal timer_finished
        timer_finished = event
        timer_finished_ready.set()

    hass.bus.async_listen_once(EVENT_TIMER_FINISHED, handle_finished)

    # --------
    # Decrease
    # --------
    await control_client.send_json_auto_id(
        {"type": "intent/timers/decrease", "timer_id": timer_id, "hours": 2}
    )
    msg = await control_client.receive_json()
    assert msg["success"]

    # updated event
    msg = await sub_client.receive_json()
    assert msg["event"]["event_type"] == "updated"
    assert msg["event"]["timer"]["id"] == timer_id
    assert msg["event"]["timer"]["seconds"] == 0

    # status
    await control_client.send_json_auto_id({"type": "intent/timers/status"})
    msg = await control_client.receive_json()
    assert msg["success"]
    assert not msg["result"]["timers"]  # timer finished

    # ------
    # Finish
    # ------
    async with asyncio.timeout(1):
        msg = await sub_client.receive_json()

        # Wait for bus event
        await timer_finished_ready.wait()

    assert msg["event"]["event_type"] == "finished"
    assert msg["event"]["timer"]["id"] == timer_id

    assert timer_finished
    assert timer_finished.data["id"] == timer_id

    # Verify custom event data
    assert timer_finished.data["test_key"] == "test_value"
