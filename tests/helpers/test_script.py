"""The tests for the Script component."""
# pylint: disable=protected-access
import asyncio
from datetime import timedelta
import logging
from unittest import mock

import asynctest
import pytest
import voluptuous as vol

# Otherwise can't test just this file (import order issue)
from homeassistant import exceptions
import homeassistant.components.scene as scene
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import Context, callback
from homeassistant.helpers import config_validation as cv, script
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

ENTITY_ID = "script.test"

_ALL_RUN_MODES = [None, "background", "blocking"]


async def test_firing_event_basic(hass):
    """Test the firing of events."""
    event = "test_event"
    context = Context()

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    schema = cv.SCRIPT_SCHEMA({"event": event, "event_data": {"hello": "world"}})

    # For this one test we'll make sure "legacy" works the same as None.
    for run_mode in _ALL_RUN_MODES + ["legacy"]:
        events = []

        if run_mode is None:
            script_obj = script.Script(hass, schema)
        else:
            script_obj = script.Script(hass, schema, run_mode=run_mode)

        assert not script_obj.can_cancel

        await script_obj.async_run(context=context)

        await hass.async_block_till_done()

        assert len(events) == 1
        assert events[0].context is context
        assert events[0].data.get("hello") == "world"
        assert not script_obj.can_cancel


async def test_firing_event_template(hass):
    """Test the firing of events."""
    event = "test_event"
    context = Context()

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    schema = cv.SCRIPT_SCHEMA(
        {
            "event": event,
            "event_data_template": {
                "dict": {
                    1: "{{ is_world }}",
                    2: "{{ is_world }}{{ is_world }}",
                    3: "{{ is_world }}{{ is_world }}{{ is_world }}",
                },
                "list": ["{{ is_world }}", "{{ is_world }}{{ is_world }}"],
            },
        }
    )

    for run_mode in _ALL_RUN_MODES:
        events = []

        if run_mode is None:
            script_obj = script.Script(hass, schema)
        else:
            script_obj = script.Script(hass, schema, run_mode=run_mode)

        assert not script_obj.can_cancel

        await script_obj.async_run({"is_world": "yes"}, context=context)

        await hass.async_block_till_done()

        assert len(events) == 1
        assert events[0].context is context
        assert events[0].data == {
            "dict": {1: "yes", 2: "yesyes", 3: "yesyesyes"},
            "list": ["yes", "yesyes"],
        }


async def test_calling_service_basic(hass):
    """Test the calling of a service."""
    context = Context()

    @callback
    def record_call(service):
        """Add recorded event to set."""
        calls.append(service)

    hass.services.async_register("test", "script", record_call)

    schema = cv.SCRIPT_SCHEMA({"service": "test.script", "data": {"hello": "world"}})

    for run_mode in _ALL_RUN_MODES:
        calls = []

        if run_mode is None:
            script_obj = script.Script(hass, schema)
        else:
            script_obj = script.Script(hass, schema, run_mode=run_mode)

        assert not script_obj.can_cancel

        await script_obj.async_run(context=context)

        await hass.async_block_till_done()

        assert len(calls) == 1
        assert calls[0].context is context
        assert calls[0].data.get("hello") == "world"


async def test_cancel_no_wait(hass, caplog):
    """Test stopping script."""
    event = "test_event"

    async def async_simulate_long_service(service):
        """Simulate a service that takes a not insignificant time."""
        await asyncio.sleep(0.01)

    hass.services.async_register("test", "script", async_simulate_long_service)

    @callback
    def monitor_event(event):
        """Signal event happened."""
        event_sem.release()

    hass.bus.async_listen(event, monitor_event)

    schema = cv.SCRIPT_SCHEMA([{"event": event}, {"service": "test.script"}])

    for run_mode in _ALL_RUN_MODES:
        event_sem = asyncio.Semaphore(0)

        if run_mode is None:
            script_obj = script.Script(hass, schema)
        else:
            script_obj = script.Script(hass, schema, run_mode=run_mode)

        tasks = []
        for _ in range(3):
            if run_mode == "background":
                await script_obj.async_run()
            else:
                hass.async_create_task(script_obj.async_run())
            tasks.append(hass.async_create_task(event_sem.acquire()))
        await asyncio.wait_for(asyncio.gather(*tasks), 1)

        # Can't assert just yet because we haven't verified stopping works yet.
        # If assert fails we can hang test if async_stop doesn't work.
        script_was_runing = script_obj.is_running

        await script_obj.async_stop()
        await hass.async_block_till_done()

        assert script_was_runing
        assert not script_obj.is_running


async def test_activating_scene(hass):
    """Test the activation of a scene."""
    context = Context()

    @callback
    def record_call(service):
        """Add recorded event to set."""
        calls.append(service)

    hass.services.async_register(scene.DOMAIN, SERVICE_TURN_ON, record_call)

    schema = cv.SCRIPT_SCHEMA({"scene": "scene.hello"})

    for run_mode in _ALL_RUN_MODES:
        calls = []

        if run_mode is None:
            script_obj = script.Script(hass, schema)
        else:
            script_obj = script.Script(hass, schema, run_mode=run_mode)

        assert not script_obj.can_cancel

        await script_obj.async_run(context=context)

        await hass.async_block_till_done()

        assert len(calls) == 1
        assert calls[0].context is context
        assert calls[0].data.get(ATTR_ENTITY_ID) == "scene.hello"


async def test_calling_service_template(hass):
    """Test the calling of a service."""
    context = Context()

    @callback
    def record_call(service):
        """Add recorded event to set."""
        calls.append(service)

    hass.services.async_register("test", "script", record_call)

    schema = cv.SCRIPT_SCHEMA(
        {
            "service_template": """
            {% if True %}
                test.script
            {% else %}
                test.not_script
            {% endif %}""",
            "data_template": {
                "hello": """
                {% if is_world == 'yes' %}
                    world
                {% else %}
                    not world
                {% endif %}
            """
            },
        }
    )

    for run_mode in _ALL_RUN_MODES:
        calls = []

        if run_mode is None:
            script_obj = script.Script(hass, schema)
        else:
            script_obj = script.Script(hass, schema, run_mode=run_mode)

        assert not script_obj.can_cancel

        await script_obj.async_run({"is_world": "yes"}, context=context)

        await hass.async_block_till_done()

        assert len(calls) == 1
        assert calls[0].context is context
        assert calls[0].data.get("hello") == "world"


async def test_multiple_runs_no_wait(hass):
    """Test multiple runs with no wait in script."""
    logger = logging.getLogger("TEST")

    async def async_simulate_long_service(service):
        """Simulate a service that takes a not insignificant time."""

        @callback
        def service_done_cb(event):
            logger.debug("simulated service (%s:%s) done", fire, listen)
            service_done.set()

        calls.append(service)

        fire = service.data.get("fire")
        listen = service.data.get("listen")
        logger.debug("simulated service (%s:%s) started", fire, listen)

        service_done = asyncio.Event()
        unsub = hass.bus.async_listen(listen, service_done_cb)

        hass.bus.async_fire(fire)

        await service_done.wait()
        unsub()

    hass.services.async_register("test", "script", async_simulate_long_service)

    heard_event = asyncio.Event()

    @callback
    def heard_event_cb(event):
        logger.debug("heard: %s", event)
        heard_event.set()

    schema = cv.SCRIPT_SCHEMA(
        [
            {
                "service": "test.script",
                "data_template": {"fire": "{{ fire1 }}", "listen": "{{ listen1 }}"},
            },
            {
                "service": "test.script",
                "data_template": {"fire": "{{ fire2 }}", "listen": "{{ listen2 }}"},
            },
        ]
    )

    for run_mode in _ALL_RUN_MODES:
        calls = []
        heard_event.clear()

        if run_mode is None:
            script_obj = script.Script(hass, schema)
        else:
            script_obj = script.Script(hass, schema, run_mode=run_mode)

        # Start script twice in such a way that second run will be started while first
        # run is in the middle of the first service call.

        unsub = hass.bus.async_listen("1", heard_event_cb)

        logger.debug("starting 1st script")
        coro = script_obj.async_run(
            {"fire1": "1", "listen1": "2", "fire2": "3", "listen2": "4"}
        )
        if run_mode == "background":
            await coro
        else:
            hass.async_create_task(coro)
        await asyncio.wait_for(heard_event.wait(), 1)

        unsub()

        logger.debug("starting 2nd script")
        await script_obj.async_run(
            {"fire1": "2", "listen1": "3", "fire2": "4", "listen2": "4"}
        )

        await hass.async_block_till_done()

        assert len(calls) == 4


async def test_delay_basic(hass):
    """Test the delay."""
    delay_alias = "delay step"
    delay_started_flag = asyncio.Event()

    @callback
    def delay_started_cb():
        delay_started_flag.set()

    delay = timedelta(milliseconds=10)
    schema = cv.SCRIPT_SCHEMA({"delay": delay, "alias": delay_alias})

    for run_mode in _ALL_RUN_MODES:
        delay_started_flag.clear()

        if run_mode is None:
            script_obj = script.Script(hass, schema, change_listener=delay_started_cb)
        else:
            script_obj = script.Script(
                hass, schema, change_listener=delay_started_cb, run_mode=run_mode
            )

        assert script_obj.can_cancel

        try:
            if run_mode == "background":
                await script_obj.async_run()
            else:
                hass.async_create_task(script_obj.async_run())
            await asyncio.wait_for(delay_started_flag.wait(), 1)

            assert script_obj.is_running
            assert script_obj.last_action == delay_alias
        except (AssertionError, asyncio.TimeoutError):
            await script_obj.async_stop()
            raise
        else:
            if run_mode in (None, "legacy"):
                future = dt_util.utcnow() + delay
                async_fire_time_changed(hass, future)
            await hass.async_block_till_done()

            assert not script_obj.is_running
            assert script_obj.last_action is None


async def test_multiple_runs_delay(hass):
    """Test multiple runs with delay in script."""
    event = "test_event"
    delay_started_flag = asyncio.Event()

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    @callback
    def delay_started_cb():
        delay_started_flag.set()

    delay = timedelta(milliseconds=10)
    schema = cv.SCRIPT_SCHEMA(
        [
            {"event": event, "event_data": {"value": 1}},
            {"delay": delay},
            {"event": event, "event_data": {"value": 2}},
        ]
    )

    for run_mode in _ALL_RUN_MODES:
        events = []
        delay_started_flag.clear()

        if run_mode is None:
            script_obj = script.Script(hass, schema, change_listener=delay_started_cb)
        else:
            script_obj = script.Script(
                hass, schema, change_listener=delay_started_cb, run_mode=run_mode
            )

        try:
            if run_mode == "background":
                await script_obj.async_run()
            else:
                hass.async_create_task(script_obj.async_run())
            await asyncio.wait_for(delay_started_flag.wait(), 1)

            assert script_obj.is_running
            assert len(events) == 1
            assert events[-1].data["value"] == 1
        except (AssertionError, asyncio.TimeoutError):
            await script_obj.async_stop()
            raise
        else:
            # Start second run of script while first run is in a delay.
            await script_obj.async_run()
            if run_mode in (None, "legacy"):
                future = dt_util.utcnow() + delay
                async_fire_time_changed(hass, future)
            await hass.async_block_till_done()

            assert not script_obj.is_running
            if run_mode in (None, "legacy"):
                assert len(events) == 2
            else:
                assert len(events) == 4
                assert events[-3].data["value"] == 1
                assert events[-2].data["value"] == 2
            assert events[-1].data["value"] == 2


async def test_delay_template_ok(hass):
    """Test the delay as a template."""
    delay_started_flag = asyncio.Event()

    @callback
    def delay_started_cb():
        delay_started_flag.set()

    schema = cv.SCRIPT_SCHEMA({"delay": "00:00:{{ 1 }}"})

    for run_mode in _ALL_RUN_MODES:
        delay_started_flag.clear()

        if run_mode is None:
            script_obj = script.Script(hass, schema, change_listener=delay_started_cb)
        else:
            script_obj = script.Script(
                hass, schema, change_listener=delay_started_cb, run_mode=run_mode
            )

        assert script_obj.can_cancel

        try:
            if run_mode == "background":
                await script_obj.async_run()
            else:
                hass.async_create_task(script_obj.async_run())
            await asyncio.wait_for(delay_started_flag.wait(), 1)
            assert script_obj.is_running
        except (AssertionError, asyncio.TimeoutError):
            await script_obj.async_stop()
            raise
        else:
            if run_mode in (None, "legacy"):
                future = dt_util.utcnow() + timedelta(seconds=1)
                async_fire_time_changed(hass, future)
            await hass.async_block_till_done()

            assert not script_obj.is_running


async def test_delay_template_invalid(hass, caplog):
    """Test the delay as a template that fails."""
    event = "test_event"

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    schema = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {"delay": "{{ invalid_delay }}"},
            {"delay": {"seconds": 5}},
            {"event": event},
        ]
    )

    for run_mode in _ALL_RUN_MODES:
        events = []

        if run_mode is None:
            script_obj = script.Script(hass, schema)
        else:
            script_obj = script.Script(hass, schema, run_mode=run_mode)
        start_idx = len(caplog.records)

        await script_obj.async_run()
        await hass.async_block_till_done()

        assert any(
            rec.levelname == "ERROR" and "Error rendering" in rec.message
            for rec in caplog.records[start_idx:]
        )

        assert not script_obj.is_running
        assert len(events) == 1


async def test_delay_template_complex_ok(hass):
    """Test the delay with a working complex template."""
    delay_started_flag = asyncio.Event()

    @callback
    def delay_started_cb():
        delay_started_flag.set()

    milliseconds = 10
    schema = cv.SCRIPT_SCHEMA({"delay": {"milliseconds": "{{ milliseconds }}"}})

    for run_mode in _ALL_RUN_MODES:
        delay_started_flag.clear()

        if run_mode is None:
            script_obj = script.Script(hass, schema, change_listener=delay_started_cb)
        else:
            script_obj = script.Script(
                hass, schema, change_listener=delay_started_cb, run_mode=run_mode
            )

        assert script_obj.can_cancel

        try:
            coro = script_obj.async_run({"milliseconds": milliseconds})
            if run_mode == "background":
                await coro
            else:
                hass.async_create_task(coro)
            await asyncio.wait_for(delay_started_flag.wait(), 1)
            assert script_obj.is_running
        except (AssertionError, asyncio.TimeoutError):
            await script_obj.async_stop()
            raise
        else:
            if run_mode in (None, "legacy"):
                future = dt_util.utcnow() + timedelta(milliseconds=milliseconds)
                async_fire_time_changed(hass, future)
            await hass.async_block_till_done()

            assert not script_obj.is_running


async def test_delay_template_complex_invalid(hass, caplog):
    """Test the delay with a complex template that fails."""
    event = "test_event"

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    schema = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {"delay": {"seconds": "{{ invalid_delay }}"}},
            {"delay": {"seconds": 5}},
            {"event": event},
        ]
    )

    for run_mode in _ALL_RUN_MODES:
        events = []

        if run_mode is None:
            script_obj = script.Script(hass, schema)
        else:
            script_obj = script.Script(hass, schema, run_mode=run_mode)
        start_idx = len(caplog.records)

        await script_obj.async_run()
        await hass.async_block_till_done()

        assert any(
            rec.levelname == "ERROR" and "Error rendering" in rec.message
            for rec in caplog.records[start_idx:]
        )

        assert not script_obj.is_running
        assert len(events) == 1


async def test_cancel_delay(hass):
    """Test the cancelling while the delay is present."""
    delay_started_flag = asyncio.Event()
    event = "test_event"

    @callback
    def delay_started_cb():
        delay_started_flag.set()

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    delay = timedelta(milliseconds=10)
    schema = cv.SCRIPT_SCHEMA([{"delay": delay}, {"event": event}])

    for run_mode in _ALL_RUN_MODES:
        delay_started_flag.clear()
        events = []

        if run_mode is None:
            script_obj = script.Script(hass, schema, change_listener=delay_started_cb)
        else:
            script_obj = script.Script(
                hass, schema, change_listener=delay_started_cb, run_mode=run_mode
            )

        try:
            if run_mode == "background":
                await script_obj.async_run()
            else:
                hass.async_create_task(script_obj.async_run())
            await asyncio.wait_for(delay_started_flag.wait(), 1)

            assert script_obj.is_running
            assert len(events) == 0
        except (AssertionError, asyncio.TimeoutError):
            await script_obj.async_stop()
            raise
        else:
            await script_obj.async_stop()

            assert not script_obj.is_running

            # Make sure the script is really stopped.

            if run_mode in (None, "legacy"):
                future = dt_util.utcnow() + delay
                async_fire_time_changed(hass, future)
            await hass.async_block_till_done()

            assert not script_obj.is_running
            assert len(events) == 0


async def test_wait_template_basic(hass):
    """Test the wait template."""
    wait_alias = "wait step"
    wait_started_flag = asyncio.Event()

    @callback
    def wait_started_cb():
        wait_started_flag.set()

    schema = cv.SCRIPT_SCHEMA(
        {
            "wait_template": "{{ states.switch.test.state == 'off' }}",
            "alias": wait_alias,
        }
    )

    for run_mode in _ALL_RUN_MODES:
        wait_started_flag.clear()
        hass.states.async_set("switch.test", "on")

        if run_mode is None:
            script_obj = script.Script(hass, schema, change_listener=wait_started_cb)
        else:
            script_obj = script.Script(
                hass, schema, change_listener=wait_started_cb, run_mode=run_mode
            )

        assert script_obj.can_cancel

        try:
            if run_mode == "background":
                await script_obj.async_run()
            else:
                hass.async_create_task(script_obj.async_run())
            await asyncio.wait_for(wait_started_flag.wait(), 1)

            assert script_obj.is_running
            assert script_obj.last_action == wait_alias
        except (AssertionError, asyncio.TimeoutError):
            await script_obj.async_stop()
            raise
        else:
            hass.states.async_set("switch.test", "off")
            await hass.async_block_till_done()

            assert not script_obj.is_running
            assert script_obj.last_action is None


async def test_multiple_runs_wait_template(hass):
    """Test multiple runs with wait_template in script."""
    event = "test_event"
    wait_started_flag = asyncio.Event()

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    @callback
    def wait_started_cb():
        wait_started_flag.set()

    schema = cv.SCRIPT_SCHEMA(
        [
            {"event": event, "event_data": {"value": 1}},
            {"wait_template": "{{ states.switch.test.state == 'off' }}"},
            {"event": event, "event_data": {"value": 2}},
        ]
    )

    for run_mode in _ALL_RUN_MODES:
        events = []
        wait_started_flag.clear()
        hass.states.async_set("switch.test", "on")

        if run_mode is None:
            script_obj = script.Script(hass, schema, change_listener=wait_started_cb)
        else:
            script_obj = script.Script(
                hass, schema, change_listener=wait_started_cb, run_mode=run_mode
            )

        try:
            if run_mode == "background":
                await script_obj.async_run()
            else:
                hass.async_create_task(script_obj.async_run())
            await asyncio.wait_for(wait_started_flag.wait(), 1)

            assert script_obj.is_running
            assert len(events) == 1
            assert events[-1].data["value"] == 1
        except (AssertionError, asyncio.TimeoutError):
            await script_obj.async_stop()
            raise
        else:
            # Start second run of script while first run is in wait_template.
            if run_mode == "blocking":
                hass.async_create_task(script_obj.async_run())
            else:
                await script_obj.async_run()
            hass.states.async_set("switch.test", "off")
            await hass.async_block_till_done()

            assert not script_obj.is_running
            if run_mode in (None, "legacy"):
                assert len(events) == 2
            else:
                assert len(events) == 4
                assert events[-3].data["value"] == 1
                assert events[-2].data["value"] == 2
            assert events[-1].data["value"] == 2


async def test_cancel_wait_template(hass):
    """Test the cancelling while wait_template is present."""
    wait_started_flag = asyncio.Event()
    event = "test_event"

    @callback
    def wait_started_cb():
        wait_started_flag.set()

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    schema = cv.SCRIPT_SCHEMA(
        [
            {"wait_template": "{{ states.switch.test.state == 'off' }}"},
            {"event": event},
        ]
    )

    for run_mode in _ALL_RUN_MODES:
        wait_started_flag.clear()
        events = []
        hass.states.async_set("switch.test", "on")

        if run_mode is None:
            script_obj = script.Script(hass, schema, change_listener=wait_started_cb)
        else:
            script_obj = script.Script(
                hass, schema, change_listener=wait_started_cb, run_mode=run_mode
            )

        try:
            if run_mode == "background":
                await script_obj.async_run()
            else:
                hass.async_create_task(script_obj.async_run())
            await asyncio.wait_for(wait_started_flag.wait(), 1)

            assert script_obj.is_running
            assert len(events) == 0
        except (AssertionError, asyncio.TimeoutError):
            await script_obj.async_stop()
            raise
        else:
            await script_obj.async_stop()

            assert not script_obj.is_running

            # Make sure the script is really stopped.

            hass.states.async_set("switch.test", "off")
            await hass.async_block_till_done()

            assert not script_obj.is_running
            assert len(events) == 0


async def test_wait_template_not_schedule(hass):
    """Test the wait template with correct condition."""
    event = "test_event"

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    hass.states.async_set("switch.test", "on")

    schema = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {"wait_template": "{{ states.switch.test.state == 'on' }}"},
            {"event": event},
        ]
    )

    for run_mode in _ALL_RUN_MODES:
        events = []

        if run_mode is None:
            script_obj = script.Script(hass, schema)
        else:
            script_obj = script.Script(hass, schema, run_mode=run_mode)

        await script_obj.async_run()
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == 2


async def test_wait_template_timeout_halt(hass):
    """Test the wait template, halt on timeout."""
    event = "test_event"
    wait_started_flag = asyncio.Event()

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    @callback
    def wait_started_cb():
        wait_started_flag.set()

    hass.states.async_set("switch.test", "on")

    timeout = timedelta(milliseconds=10)
    schema = cv.SCRIPT_SCHEMA(
        [
            {
                "wait_template": "{{ states.switch.test.state == 'off' }}",
                "continue_on_timeout": False,
                "timeout": timeout,
            },
            {"event": event},
        ]
    )

    for run_mode in _ALL_RUN_MODES:
        events = []
        wait_started_flag.clear()

        if run_mode is None:
            script_obj = script.Script(hass, schema, change_listener=wait_started_cb)
        else:
            script_obj = script.Script(
                hass, schema, change_listener=wait_started_cb, run_mode=run_mode
            )

        try:
            if run_mode == "background":
                await script_obj.async_run()
            else:
                hass.async_create_task(script_obj.async_run())
            await asyncio.wait_for(wait_started_flag.wait(), 1)

            assert script_obj.is_running
            assert len(events) == 0
        except (AssertionError, asyncio.TimeoutError):
            await script_obj.async_stop()
            raise
        else:
            if run_mode in (None, "legacy"):
                future = dt_util.utcnow() + timeout
                async_fire_time_changed(hass, future)
            await hass.async_block_till_done()

            assert not script_obj.is_running
            assert len(events) == 0


async def test_wait_template_timeout_continue(hass):
    """Test the wait template with continuing the script."""
    event = "test_event"
    wait_started_flag = asyncio.Event()

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    @callback
    def wait_started_cb():
        wait_started_flag.set()

    hass.states.async_set("switch.test", "on")

    timeout = timedelta(milliseconds=10)
    schema = cv.SCRIPT_SCHEMA(
        [
            {
                "wait_template": "{{ states.switch.test.state == 'off' }}",
                "continue_on_timeout": True,
                "timeout": timeout,
            },
            {"event": event},
        ]
    )

    for run_mode in _ALL_RUN_MODES:
        events = []
        wait_started_flag.clear()

        if run_mode is None:
            script_obj = script.Script(hass, schema, change_listener=wait_started_cb)
        else:
            script_obj = script.Script(
                hass, schema, change_listener=wait_started_cb, run_mode=run_mode
            )

        try:
            if run_mode == "background":
                await script_obj.async_run()
            else:
                hass.async_create_task(script_obj.async_run())
            await asyncio.wait_for(wait_started_flag.wait(), 1)

            assert script_obj.is_running
            assert len(events) == 0
        except (AssertionError, asyncio.TimeoutError):
            await script_obj.async_stop()
            raise
        else:
            if run_mode in (None, "legacy"):
                future = dt_util.utcnow() + timeout
                async_fire_time_changed(hass, future)
            await hass.async_block_till_done()

            assert not script_obj.is_running
            assert len(events) == 1


async def test_wait_template_timeout_default(hass):
    """Test the wait template with default continue."""
    event = "test_event"
    wait_started_flag = asyncio.Event()

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    @callback
    def wait_started_cb():
        wait_started_flag.set()

    hass.states.async_set("switch.test", "on")

    timeout = timedelta(milliseconds=10)
    schema = cv.SCRIPT_SCHEMA(
        [
            {
                "wait_template": "{{ states.switch.test.state == 'off' }}",
                "timeout": timeout,
            },
            {"event": event},
        ]
    )

    for run_mode in _ALL_RUN_MODES:
        events = []
        wait_started_flag.clear()

        if run_mode is None:
            script_obj = script.Script(hass, schema, change_listener=wait_started_cb)
        else:
            script_obj = script.Script(
                hass, schema, change_listener=wait_started_cb, run_mode=run_mode
            )

        try:
            if run_mode == "background":
                await script_obj.async_run()
            else:
                hass.async_create_task(script_obj.async_run())
            await asyncio.wait_for(wait_started_flag.wait(), 1)

            assert script_obj.is_running
            assert len(events) == 0
        except (AssertionError, asyncio.TimeoutError):
            await script_obj.async_stop()
            raise
        else:
            if run_mode in (None, "legacy"):
                future = dt_util.utcnow() + timeout
                async_fire_time_changed(hass, future)
            await hass.async_block_till_done()

            assert not script_obj.is_running
            assert len(events) == 1


async def test_wait_template_variables(hass):
    """Test the wait template with variables."""
    wait_started_flag = asyncio.Event()

    @callback
    def wait_started_cb():
        wait_started_flag.set()

    schema = cv.SCRIPT_SCHEMA({"wait_template": "{{ is_state(data, 'off') }}"})

    for run_mode in _ALL_RUN_MODES:
        wait_started_flag.clear()
        hass.states.async_set("switch.test", "on")

        if run_mode is None:
            script_obj = script.Script(hass, schema, change_listener=wait_started_cb)
        else:
            script_obj = script.Script(
                hass, schema, change_listener=wait_started_cb, run_mode=run_mode
            )

        assert script_obj.can_cancel

        try:
            coro = script_obj.async_run({"data": "switch.test"})
            if run_mode == "background":
                await coro
            else:
                hass.async_create_task(coro)
            await asyncio.wait_for(wait_started_flag.wait(), 1)

            assert script_obj.is_running
        except (AssertionError, asyncio.TimeoutError):
            await script_obj.async_stop()
            raise
        else:
            hass.states.async_set("switch.test", "off")
            await hass.async_block_till_done()

            assert not script_obj.is_running


async def test_condition_basic(hass):
    """Test if we can use conditions in a script."""
    event = "test_event"
    events = []

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    schema = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {
                "condition": "template",
                "value_template": "{{ states.test.entity.state == 'hello' }}",
            },
            {"event": event},
        ]
    )

    for run_mode in _ALL_RUN_MODES:
        events = []
        hass.states.async_set("test.entity", "hello")

        if run_mode is None:
            script_obj = script.Script(hass, schema)
        else:
            script_obj = script.Script(hass, schema, run_mode=run_mode)

        assert not script_obj.can_cancel

        await script_obj.async_run()
        await hass.async_block_till_done()

        assert len(events) == 2

        hass.states.async_set("test.entity", "goodbye")

        await script_obj.async_run()
        await hass.async_block_till_done()

        assert len(events) == 3


@asynctest.patch("homeassistant.helpers.script.condition.async_from_config")
async def test_condition_created_once(async_from_config, hass):
    """Test that the conditions do not get created multiple times."""
    event = "test_event"
    events = []

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    hass.states.async_set("test.entity", "hello")

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event},
                {
                    "condition": "template",
                    "value_template": '{{ states.test.entity.state == "hello" }}',
                },
                {"event": event},
            ]
        ),
    )

    await script_obj.async_run()
    await script_obj.async_run()
    await hass.async_block_till_done()
    assert async_from_config.call_count == 1
    assert len(script_obj._config_cache) == 1


async def test_condition_all_cached(hass):
    """Test that multiple conditions get cached."""
    event = "test_event"
    events = []

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    hass.states.async_set("test.entity", "hello")

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event},
                {
                    "condition": "template",
                    "value_template": '{{ states.test.entity.state == "hello" }}',
                },
                {
                    "condition": "template",
                    "value_template": '{{ states.test.entity.state != "hello" }}',
                },
                {"event": event},
            ]
        ),
    )

    await script_obj.async_run()
    await hass.async_block_till_done()
    assert len(script_obj._config_cache) == 2


async def test_last_triggered(hass):
    """Test the last_triggered."""
    event = "test_event"

    schema = cv.SCRIPT_SCHEMA({"event": event})

    for run_mode in _ALL_RUN_MODES:
        if run_mode is None:
            script_obj = script.Script(hass, schema)
        else:
            script_obj = script.Script(hass, schema, run_mode=run_mode)

        assert script_obj.last_triggered is None

        time = dt_util.utcnow()
        with mock.patch("homeassistant.helpers.script.utcnow", return_value=time):
            await script_obj.async_run()
            await hass.async_block_till_done()

        assert script_obj.last_triggered == time


async def test_propagate_error_service_not_found(hass):
    """Test that a script aborts when a service is not found."""
    event = "test_event"

    @callback
    def record_event(event):
        events.append(event)

    hass.bus.async_listen(event, record_event)

    schema = cv.SCRIPT_SCHEMA([{"service": "test.script"}, {"event": event}])

    run_modes = _ALL_RUN_MODES
    if "background" in run_modes:
        run_modes.remove("background")
    for run_mode in run_modes:
        events = []

        if run_mode is None:
            script_obj = script.Script(hass, schema)
        else:
            script_obj = script.Script(hass, schema, run_mode=run_mode)

        with pytest.raises(exceptions.ServiceNotFound):
            await script_obj.async_run()

        assert len(events) == 0
        assert not script_obj.is_running


async def test_propagate_error_invalid_service_data(hass):
    """Test that a script aborts when we send invalid service data."""
    event = "test_event"

    @callback
    def record_event(event):
        events.append(event)

    hass.bus.async_listen(event, record_event)

    @callback
    def record_call(service):
        """Add recorded event to set."""
        calls.append(service)

    hass.services.async_register(
        "test", "script", record_call, schema=vol.Schema({"text": str})
    )

    schema = cv.SCRIPT_SCHEMA(
        [{"service": "test.script", "data": {"text": 1}}, {"event": event}]
    )

    run_modes = _ALL_RUN_MODES
    if "background" in run_modes:
        run_modes.remove("background")
    for run_mode in run_modes:
        events = []
        calls = []

        if run_mode is None:
            script_obj = script.Script(hass, schema)
        else:
            script_obj = script.Script(hass, schema, run_mode=run_mode)

        with pytest.raises(vol.Invalid):
            await script_obj.async_run()

        assert len(events) == 0
        assert len(calls) == 0
        assert not script_obj.is_running


async def test_propagate_error_service_exception(hass):
    """Test that a script aborts when a service throws an exception."""
    event = "test_event"

    @callback
    def record_event(event):
        events.append(event)

    hass.bus.async_listen(event, record_event)

    @callback
    def record_call(service):
        """Add recorded event to set."""
        raise ValueError("BROKEN")

    hass.services.async_register("test", "script", record_call)

    schema = cv.SCRIPT_SCHEMA([{"service": "test.script"}, {"event": event}])

    run_modes = _ALL_RUN_MODES
    if "background" in run_modes:
        run_modes.remove("background")
    for run_mode in run_modes:
        events = []

        if run_mode is None:
            script_obj = script.Script(hass, schema)
        else:
            script_obj = script.Script(hass, schema, run_mode=run_mode)

        with pytest.raises(ValueError):
            await script_obj.async_run()

        assert len(events) == 0
        assert not script_obj.is_running


async def test_referenced_entities():
    """Test referenced entities."""
    script_obj = script.Script(
        None,
        cv.SCRIPT_SCHEMA(
            [
                {
                    "service": "test.script",
                    "data": {"entity_id": "light.service_not_list"},
                },
                {
                    "service": "test.script",
                    "data": {"entity_id": ["light.service_list"]},
                },
                {
                    "condition": "state",
                    "entity_id": "sensor.condition",
                    "state": "100",
                },
                {"service": "test.script", "data": {"without": "entity_id"}},
                {"scene": "scene.hello"},
                {"event": "test_event"},
                {"delay": "{{ delay_period }}"},
            ]
        ),
    )
    assert script_obj.referenced_entities == {
        "light.service_not_list",
        "light.service_list",
        "sensor.condition",
        "scene.hello",
    }
    # Test we cache results.
    assert script_obj.referenced_entities is script_obj.referenced_entities


async def test_referenced_devices():
    """Test referenced entities."""
    script_obj = script.Script(
        None,
        cv.SCRIPT_SCHEMA(
            [
                {"domain": "light", "device_id": "script-dev-id"},
                {
                    "condition": "device",
                    "device_id": "condition-dev-id",
                    "domain": "switch",
                },
            ]
        ),
    )
    assert script_obj.referenced_devices == {"script-dev-id", "condition-dev-id"}
    # Test we cache results.
    assert script_obj.referenced_devices is script_obj.referenced_devices


async def test_if_running_with_legacy_run_mode(hass, caplog):
    """Test using if_running with run_mode='legacy'."""
    # TODO: REMOVE
    if _ALL_RUN_MODES == [None]:
        return

    with pytest.raises(exceptions.HomeAssistantError):
        script.Script(
            hass,
            [],
            if_running="ignore",
            run_mode="legacy",
            logger=logging.getLogger("TEST"),
        )
    assert any(
        rec.levelname == "ERROR"
        and rec.name == "TEST"
        and all(text in rec.message for text in ("if_running", "legacy"))
        for rec in caplog.records
    )


async def test_if_running_ignore(hass, caplog):
    """Test overlapping runs with if_running='ignore'."""
    # TODO: REMOVE
    if _ALL_RUN_MODES == [None]:
        return

    event = "test_event"
    events = []
    wait_started_flag = asyncio.Event()

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    @callback
    def wait_started_cb():
        wait_started_flag.set()

    hass.states.async_set("switch.test", "on")

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event, "event_data": {"value": 1}},
                {"wait_template": "{{ states.switch.test.state == 'off' }}"},
                {"event": event, "event_data": {"value": 2}},
            ]
        ),
        change_listener=wait_started_cb,
        if_running="ignore",
        run_mode="background",
        logger=logging.getLogger("TEST"),
    )

    try:
        await script_obj.async_run()
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 1
        assert events[0].data["value"] == 1

        # Start second run of script while first run is suspended in wait_template.
        # This should ignore second run.

        await script_obj.async_run()

        assert script_obj.is_running
        assert any(
            rec.levelname == "INFO" and rec.name == "TEST" and "Skipping" in rec.message
            for rec in caplog.records
        )
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        hass.states.async_set("switch.test", "off")
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == 2
        assert events[1].data["value"] == 2


async def test_if_running_error(hass, caplog):
    """Test overlapping runs with if_running='error'."""
    # TODO: REMOVE
    if _ALL_RUN_MODES == [None]:
        return

    event = "test_event"
    events = []
    wait_started_flag = asyncio.Event()

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    @callback
    def wait_started_cb():
        wait_started_flag.set()

    hass.states.async_set("switch.test", "on")

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event, "event_data": {"value": 1}},
                {"wait_template": "{{ states.switch.test.state == 'off' }}"},
                {"event": event, "event_data": {"value": 2}},
            ]
        ),
        change_listener=wait_started_cb,
        if_running="error",
        run_mode="background",
        logger=logging.getLogger("TEST"),
    )

    try:
        await script_obj.async_run()
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 1
        assert events[0].data["value"] == 1

        # Start second run of script while first run is suspended in wait_template.
        # This should cause an error.

        with pytest.raises(exceptions.HomeAssistantError):
            await script_obj.async_run()

        assert script_obj.is_running
        assert any(
            rec.levelname == "ERROR"
            and rec.name == "TEST"
            and "Already running" in rec.message
            for rec in caplog.records
        )
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        hass.states.async_set("switch.test", "off")
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == 2
        assert events[1].data["value"] == 2


async def test_if_running_restart(hass, caplog):
    """Test overlapping runs with if_running='restart'."""
    # TODO: REMOVE
    if _ALL_RUN_MODES == [None]:
        return

    event = "test_event"
    events = []
    wait_started_flag = asyncio.Event()

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    @callback
    def wait_started_cb():
        wait_started_flag.set()

    hass.states.async_set("switch.test", "on")

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event, "event_data": {"value": 1}},
                {"wait_template": "{{ states.switch.test.state == 'off' }}"},
                {"event": event, "event_data": {"value": 2}},
            ]
        ),
        change_listener=wait_started_cb,
        if_running="restart",
        run_mode="background",
        logger=logging.getLogger("TEST"),
    )

    try:
        await script_obj.async_run()
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 1
        assert events[0].data["value"] == 1

        # Start second run of script while first run is suspended in wait_template.
        # This should stop first run then start a new run.

        wait_started_flag.clear()
        await script_obj.async_run()
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 2
        assert events[1].data["value"] == 1
        assert any(
            rec.levelname == "INFO"
            and rec.name == "TEST"
            and "Restarting" in rec.message
            for rec in caplog.records
        )
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        hass.states.async_set("switch.test", "off")
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == 3
        assert events[2].data["value"] == 2


async def test_if_running_parallel(hass):
    """Test overlapping runs with if_running='parallel'."""
    # TODO: REMOVE
    if _ALL_RUN_MODES == [None]:
        return

    event = "test_event"
    events = []
    wait_started_flag = asyncio.Event()

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    @callback
    def wait_started_cb():
        wait_started_flag.set()

    hass.states.async_set("switch.test", "on")

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event, "event_data": {"value": 1}},
                {"wait_template": "{{ states.switch.test.state == 'off' }}"},
                {"event": event, "event_data": {"value": 2}},
            ]
        ),
        change_listener=wait_started_cb,
        if_running="parallel",
        run_mode="background",
        logger=logging.getLogger("TEST"),
    )

    try:
        await script_obj.async_run()
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 1
        assert events[0].data["value"] == 1

        # Start second run of script while first run is suspended in wait_template.
        # This should start a new, independent run.

        wait_started_flag.clear()
        await script_obj.async_run()
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 2
        assert events[1].data["value"] == 1
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        hass.states.async_set("switch.test", "off")
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == 4
        assert events[2].data["value"] == 2
        assert events[3].data["value"] == 2
