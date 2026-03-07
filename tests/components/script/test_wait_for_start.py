"""The tests for the Script component wait_for_start feature."""

import asyncio
import contextlib

import pytest

from homeassistant.components.script import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


async def test_wait_for_start(hass: HomeAssistant) -> None:
    """Test wait_for_start."""
    calls = async_mock_service(hass, "test", "script")

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test_script": {
                    "mode": "queued",
                    "max": 2,
                    "sequence": [
                        {"action": "test.script", "data": {"value": "start"}},
                        {"wait_template": "{{ is_state('input_boolean.wait', 'on') }}"},
                        {
                            "service": "input_boolean.turn_off",
                            "entity_id": "input_boolean.wait",
                        },
                        {"action": "test.script", "data": {"value": "end"}},
                    ],
                }
            }
        },
    )

    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"wait": {}}}
    )

    # Start the first run (background)
    hass.async_create_task(
        hass.services.async_call(
            DOMAIN, "turn_on", {ATTR_ENTITY_ID: "script.test_script"}
        )
    )

    # Wait for it to start
    await asyncio.sleep(0.1)
    assert len(calls) == 1
    assert calls[0].data["value"] == "start"

    # Start the second run with wait_for_start=True
    # This should block until the first run finishes
    task = hass.async_create_task(
        hass.services.async_call(
            DOMAIN,
            "turn_on",
            {ATTR_ENTITY_ID: "script.test_script", "wait_for_start": True},
            blocking=True,
        )
    )

    # It should not be done yet because first run is still running
    await asyncio.sleep(0.1)
    assert not task.done()

    # Finish the first run
    hass.states.async_set("input_boolean.wait", "on")
    # We can't use async_block_till_done here because 'task' is tracked and it is blocked,
    # so async_block_till_done would wait for it forever (or until timeout).
    # We just need to let the event loop run so the state change is processed.
    await asyncio.sleep(0.1)

    # Now the first run should have finished (and turned off input_boolean).
    # The second run should have started.
    # The task (turn_on call) should be done.
    assert task.done()

    # And the second run should have started
    # calls: start1, end1, start2
    assert len(calls) >= 3
    assert calls[2].data["value"] == "start"

    # But the second run should NOT be finished yet (it waits for template, which is off now)
    # So we shouldn't see end2
    assert len(calls) == 3

    # Now finish the second run
    hass.states.async_set("input_boolean.wait", "on")
    await hass.async_block_till_done()

    assert len(calls) == 4
    assert calls[3].data["value"] == "end"


async def test_wait_for_start_single_mode(hass: HomeAssistant) -> None:
    """Test wait_for_start with single mode (no queue)."""
    calls = async_mock_service(hass, "test", "script")

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test_script": {
                    "mode": "single",
                    "sequence": [
                        {"action": "test.script", "data": {"value": "run"}},
                    ],
                }
            }
        },
    )

    # Start the run with wait_for_start=True
    # It should return immediately as there is no queue
    await hass.services.async_call(
        DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: "script.test_script", "wait_for_start": True},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data["value"] == "run"


async def test_wait_for_start_cancellation(hass: HomeAssistant) -> None:
    """Test cancelling wait_for_start does not cancel the script."""
    calls = async_mock_service(hass, "test", "script")

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test_script": {
                    "mode": "queued",
                    "max": 2,
                    "sequence": [
                        {"action": "test.script", "data": {"value": "start"}},
                        {"wait_template": "{{ is_state('input_boolean.wait', 'on') }}"},
                        {"action": "test.script", "data": {"value": "end"}},
                    ],
                }
            }
        },
    )

    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"wait": {}}}
    )

    # Start the first run (background)
    hass.async_create_task(
        hass.services.async_call(
            DOMAIN, "turn_on", {ATTR_ENTITY_ID: "script.test_script"}
        )
    )

    # Wait for it to start
    await asyncio.sleep(0.1)
    assert len(calls) == 1

    # Start the second run with wait_for_start=True
    task = hass.async_create_task(
        hass.services.async_call(
            DOMAIN,
            "turn_on",
            {ATTR_ENTITY_ID: "script.test_script", "wait_for_start": True},
            blocking=True,
        )
    )

    # It should be blocked
    await asyncio.sleep(0.1)
    assert not task.done()

    # Cancel the waiting task
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    # Finish the first run
    hass.states.async_set("input_boolean.wait", "on")
    await hass.async_block_till_done()

    # The second run should still have executed because the script was queued
    # before the task was cancelled. Both runs complete:
    # calls: start1, end1, start2, end2
    assert len(calls) == 4
    assert calls[2].data["value"] == "start"
    assert calls[3].data["value"] == "end"


async def test_wait_for_start_multiple_scripts(hass: HomeAssistant) -> None:
    """Test wait_for_start with multiple scripts."""
    calls = async_mock_service(hass, "test", "script")

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test_script_1": {
                    "mode": "queued",
                    "max": 2,
                    "sequence": [
                        {"action": "test.script", "data": {"value": "start_1"}},
                        {
                            "wait_template": "{{ is_state('input_boolean.wait_1', 'on') }}"
                        },
                        {
                            "service": "input_boolean.turn_off",
                            "entity_id": "input_boolean.wait_1",
                        },
                        {"action": "test.script", "data": {"value": "end_1"}},
                    ],
                },
                "test_script_2": {
                    "mode": "queued",
                    "max": 2,
                    "sequence": [
                        {"action": "test.script", "data": {"value": "start_2"}},
                        {
                            "wait_template": "{{ is_state('input_boolean.wait_2', 'on') }}"
                        },
                        {
                            "service": "input_boolean.turn_off",
                            "entity_id": "input_boolean.wait_2",
                        },
                        {"action": "test.script", "data": {"value": "end_2"}},
                    ],
                },
            }
        },
    )

    assert await async_setup_component(
        hass,
        "input_boolean",
        {"input_boolean": {"wait_1": {}, "wait_2": {}}},
    )

    # Start the first run for both scripts (background)
    hass.async_create_task(
        hass.services.async_call(
            DOMAIN, "turn_on", {ATTR_ENTITY_ID: "script.test_script_1"}
        )
    )
    hass.async_create_task(
        hass.services.async_call(
            DOMAIN, "turn_on", {ATTR_ENTITY_ID: "script.test_script_2"}
        )
    )

    # Wait for them to start
    await asyncio.sleep(0.1)
    assert len(calls) == 2
    call_values = {c.data["value"] for c in calls}
    assert call_values == {"start_1", "start_2"}
    calls.clear()

    # Start the second run for both scripts with wait_for_start=True
    # This should block until both first runs finish
    task = hass.async_create_task(
        hass.services.async_call(
            DOMAIN,
            "turn_on",
            {
                ATTR_ENTITY_ID: ["script.test_script_1", "script.test_script_2"],
                "wait_for_start": True,
            },
            blocking=True,
        )
    )

    # It should be blocked
    await asyncio.sleep(0.1)
    assert not task.done()

    # Verify both scripts have 2 runs (1 running, 1 queued)
    # This confirms that both scripts were queued simultaneously
    state_1 = hass.states.get("script.test_script_1")
    assert state_1 is not None
    assert state_1.attributes["current"] == 2

    state_2 = hass.states.get("script.test_script_2")
    assert state_2 is not None
    assert state_2.attributes["current"] == 2

    # Finish the first run of script 1
    hass.states.async_set("input_boolean.wait_1", "on")
    await asyncio.sleep(0.1)

    # Script 1 second run should have started
    assert len(calls) == 2
    call_values = {c.data["value"] for c in calls}
    assert call_values == {"end_1", "start_1"}
    calls.clear()

    # But the task should still be blocked because script 2 hasn't started its second run
    assert not task.done()

    # Finish the first run of script 2
    hass.states.async_set("input_boolean.wait_2", "on")
    await asyncio.sleep(0.1)

    # Script 2 second run should have started
    assert len(calls) == 2
    call_values = {c.data["value"] for c in calls}
    assert call_values == {"end_2", "start_2"}

    # Now the task should be done
    assert task.done()
    await task


async def test_wait_for_start_failure_single_mode(hass: HomeAssistant) -> None:
    """Test wait_for_start does not hang when script cannot start (single mode)."""
    calls = async_mock_service(hass, "test", "script")

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test_script": {
                    "mode": "single",
                    "sequence": [
                        {"action": "test.script", "data": {"value": "start"}},
                        {"wait_template": "{{ is_state('input_boolean.wait', 'on') }}"},
                    ],
                }
            }
        },
    )

    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"wait": {}}}
    )

    # Start the first run (background)
    hass.async_create_task(
        hass.services.async_call(
            DOMAIN, "turn_on", {ATTR_ENTITY_ID: "script.test_script"}
        )
    )

    # Wait for it to start
    await asyncio.sleep(0.1)
    assert len(calls) == 1

    # Try to start the second run with wait_for_start=True
    # This should fail immediately because mode is single and it's already running
    # It should NOT hang
    try:
        await asyncio.wait_for(
            hass.services.async_call(
                DOMAIN,
                "turn_on",
                {
                    ATTR_ENTITY_ID: "script.test_script",
                    "wait_for_start": True,
                },
                blocking=True,
            ),
            timeout=1.0,
        )
    except TimeoutError:
        pytest.fail("wait_for_start hung when script could not start")

    # Try to start the third run with wait_for_start=False (default)
    # This should also NOT hang
    try:
        await asyncio.wait_for(
            hass.services.async_call(
                DOMAIN,
                "turn_on",
                {
                    ATTR_ENTITY_ID: "script.test_script",
                    "wait_for_start": False,
                },
                blocking=True,
            ),
            timeout=1.0,
        )
    except TimeoutError:
        pytest.fail("turn_on hung when script could not start")

    # Clean up
    hass.states.async_set("input_boolean.wait", "on")
    await asyncio.sleep(0.1)
