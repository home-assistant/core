"""The tests for the Script component."""
# pylint: disable=protected-access
import asyncio
from contextlib import contextmanager
from datetime import timedelta
import logging
from unittest import mock

import pytest
import voluptuous as vol

# Otherwise can't test just this file (import order issue)
from homeassistant import exceptions
import homeassistant.components.scene as scene
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import Context, callback
from homeassistant.helpers import config_validation as cv, script
from homeassistant.helpers.event import async_call_later
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

ENTITY_ID = "script.test"


@pytest.fixture
def mock_timeout(hass, monkeypatch):
    """Mock async_timeout.timeout."""

    class MockTimeout:
        def __init__(self, timeout):
            self._timeout = timeout
            self._loop = asyncio.get_event_loop()
            self._task = None
            self._cancelled = False
            self._unsub = None

        async def __aenter__(self):
            if self._timeout is None:
                return self
            self._task = asyncio.Task.current_task()
            if self._timeout <= 0:
                self._loop.call_soon(self._cancel_task)
                return self
            # Wait for a time_changed event instead of real time passing.
            self._unsub = async_call_later(hass, self._timeout, self._cancel_task)
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if exc_type is asyncio.CancelledError and self._cancelled:
                self._unsub = None
                self._task = None
                raise asyncio.TimeoutError
            if self._timeout is not None and self._unsub:
                self._unsub()
                self._unsub = None
            self._task = None
            return None

        @callback
        def _cancel_task(self, now=None):
            if self._task is not None:
                self._task.cancel()
                self._cancelled = True

    monkeypatch.setattr(script, "timeout", MockTimeout)


def async_watch_for_action(script_obj, message):
    """Watch for message in last_action."""
    flag = asyncio.Event()

    @callback
    def check_action():
        if script_obj.last_action and message in script_obj.last_action:
            flag.set()

    script_obj.change_listener = check_action
    return flag


async def test_firing_event_basic(hass):
    """Test the firing of events."""
    event = "test_event"
    context = Context()
    events = async_capture_events(hass, event)

    sequence = cv.SCRIPT_SCHEMA({"event": event, "event_data": {"hello": "world"}})
    script_obj = script.Script(hass, sequence)

    assert script_obj.can_cancel

    await script_obj.async_run(context=context)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].context is context
    assert events[0].data.get("hello") == "world"
    assert script_obj.can_cancel


async def test_firing_event_template(hass):
    """Test the firing of events."""
    event = "test_event"
    context = Context()
    events = async_capture_events(hass, event)

    sequence = cv.SCRIPT_SCHEMA(
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
    script_obj = script.Script(hass, sequence)

    assert script_obj.can_cancel

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
    calls = async_mock_service(hass, "test", "script")

    sequence = cv.SCRIPT_SCHEMA({"service": "test.script", "data": {"hello": "world"}})
    script_obj = script.Script(hass, sequence)

    assert script_obj.can_cancel

    await script_obj.async_run(context=context)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].context is context
    assert calls[0].data.get("hello") == "world"


async def test_calling_service_template(hass):
    """Test the calling of a service."""
    context = Context()
    calls = async_mock_service(hass, "test", "script")

    sequence = cv.SCRIPT_SCHEMA(
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
    script_obj = script.Script(hass, sequence)

    assert script_obj.can_cancel

    await script_obj.async_run({"is_world": "yes"}, context=context)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].context is context
    assert calls[0].data.get("hello") == "world"


async def test_multiple_runs_no_wait(hass):
    """Test multiple runs with no wait in script."""
    logger = logging.getLogger("TEST")
    calls = []
    heard_event = asyncio.Event()

    async def async_simulate_long_service(service):
        """Simulate a service that takes a not insignificant time."""
        fire = service.data.get("fire")
        listen = service.data.get("listen")
        service_done = asyncio.Event()

        @callback
        def service_done_cb(event):
            logger.debug("simulated service (%s:%s) done", fire, listen)
            service_done.set()

        calls.append(service)
        logger.debug("simulated service (%s:%s) started", fire, listen)
        unsub = hass.bus.async_listen(listen, service_done_cb)
        hass.bus.async_fire(fire)
        await service_done.wait()
        unsub()

    hass.services.async_register("test", "script", async_simulate_long_service)

    @callback
    def heard_event_cb(event):
        logger.debug("heard: %s", event)
        heard_event.set()

    sequence = cv.SCRIPT_SCHEMA(
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
    script_obj = script.Script(hass, sequence, script_mode="parallel", max_runs=2)

    # Start script twice in such a way that second run will be started while first run
    # is in the middle of the first service call.

    unsub = hass.bus.async_listen("1", heard_event_cb)
    logger.debug("starting 1st script")
    hass.async_create_task(
        script_obj.async_run(
            {"fire1": "1", "listen1": "2", "fire2": "3", "listen2": "4"}
        )
    )
    await asyncio.wait_for(heard_event.wait(), 1)
    unsub()

    logger.debug("starting 2nd script")
    await script_obj.async_run(
        {"fire1": "2", "listen1": "3", "fire2": "4", "listen2": "4"}
    )
    await hass.async_block_till_done()

    assert len(calls) == 4


async def test_activating_scene(hass):
    """Test the activation of a scene."""
    context = Context()
    calls = async_mock_service(hass, scene.DOMAIN, SERVICE_TURN_ON)

    sequence = cv.SCRIPT_SCHEMA({"scene": "scene.hello"})
    script_obj = script.Script(hass, sequence)

    assert script_obj.can_cancel

    await script_obj.async_run(context=context)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].context is context
    assert calls[0].data.get(ATTR_ENTITY_ID) == "scene.hello"


@pytest.mark.parametrize("count", [1, 3])
async def test_stop_no_wait(hass, caplog, count):
    """Test stopping script."""
    service_started_sem = asyncio.Semaphore(0)
    finish_service_event = asyncio.Event()
    event = "test_event"
    events = async_capture_events(hass, event)

    async def async_simulate_long_service(service):
        """Simulate a service that takes a not insignificant time."""
        service_started_sem.release()
        await finish_service_event.wait()

    hass.services.async_register("test", "script", async_simulate_long_service)

    sequence = cv.SCRIPT_SCHEMA([{"service": "test.script"}, {"event": event}])
    script_obj = script.Script(hass, sequence, script_mode="parallel", max_runs=count)

    # Get script started specified number of times and wait until the test.script
    # service has started for each run.
    tasks = []
    for _ in range(count):
        hass.async_create_task(script_obj.async_run())
        tasks.append(hass.async_create_task(service_started_sem.acquire()))
    await asyncio.wait_for(asyncio.gather(*tasks), 1)

    # Can't assert just yet because we haven't verified stopping works yet.
    # If assert fails we can hang test if async_stop doesn't work.
    script_was_runing = script_obj.is_running
    were_no_events = len(events) == 0

    # Begin the process of stopping the script (which should stop all runs), and then
    # let the service calls complete.
    hass.async_create_task(script_obj.async_stop())
    finish_service_event.set()

    await hass.async_block_till_done()

    assert script_was_runing
    assert were_no_events
    assert not script_obj.is_running
    assert len(events) == 0


async def test_delay_basic(hass, mock_timeout):
    """Test the delay."""
    delay_alias = "delay step"
    sequence = cv.SCRIPT_SCHEMA({"delay": {"seconds": 5}, "alias": delay_alias})
    script_obj = script.Script(hass, sequence)
    delay_started_flag = async_watch_for_action(script_obj, delay_alias)

    assert script_obj.can_cancel

    try:
        hass.async_create_task(script_obj.async_run())
        await asyncio.wait_for(delay_started_flag.wait(), 1)

        assert script_obj.is_running
        assert script_obj.last_action == delay_alias
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert script_obj.last_action is None


async def test_multiple_runs_delay(hass, mock_timeout):
    """Test multiple runs with delay in script."""
    event = "test_event"
    events = async_capture_events(hass, event)
    delay = timedelta(seconds=5)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event, "event_data": {"value": 1}},
            {"delay": delay},
            {"event": event, "event_data": {"value": 2}},
        ]
    )
    script_obj = script.Script(hass, sequence, script_mode="parallel", max_runs=2)
    delay_started_flag = async_watch_for_action(script_obj, "delay")

    try:
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
        script_obj.sequence[1]["alias"] = "delay run 2"
        delay_started_flag = async_watch_for_action(script_obj, "delay run 2")
        hass.async_create_task(script_obj.async_run())
        await asyncio.wait_for(delay_started_flag.wait(), 1)
        async_fire_time_changed(hass, dt_util.utcnow() + delay)
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == 4
        assert events[-3].data["value"] == 1
        assert events[-2].data["value"] == 2
        assert events[-1].data["value"] == 2


async def test_delay_template_ok(hass, mock_timeout):
    """Test the delay as a template."""
    sequence = cv.SCRIPT_SCHEMA({"delay": "00:00:{{ 5 }}"})
    script_obj = script.Script(hass, sequence)
    delay_started_flag = async_watch_for_action(script_obj, "delay")

    assert script_obj.can_cancel

    try:
        hass.async_create_task(script_obj.async_run())
        await asyncio.wait_for(delay_started_flag.wait(), 1)

        assert script_obj.is_running
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done()

        assert not script_obj.is_running


async def test_delay_template_invalid(hass, caplog):
    """Test the delay as a template that fails."""
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {"delay": "{{ invalid_delay }}"},
            {"delay": {"seconds": 5}},
            {"event": event},
        ]
    )
    script_obj = script.Script(hass, sequence)
    start_idx = len(caplog.records)

    await script_obj.async_run()
    await hass.async_block_till_done()

    assert any(
        rec.levelname == "ERROR" and "Error rendering" in rec.message
        for rec in caplog.records[start_idx:]
    )

    assert not script_obj.is_running
    assert len(events) == 1


async def test_delay_template_complex_ok(hass, mock_timeout):
    """Test the delay with a working complex template."""
    sequence = cv.SCRIPT_SCHEMA({"delay": {"seconds": "{{ 5 }}"}})
    script_obj = script.Script(hass, sequence)
    delay_started_flag = async_watch_for_action(script_obj, "delay")

    assert script_obj.can_cancel

    try:
        hass.async_create_task(script_obj.async_run())
        await asyncio.wait_for(delay_started_flag.wait(), 1)
        assert script_obj.is_running
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done()

        assert not script_obj.is_running


async def test_delay_template_complex_invalid(hass, caplog):
    """Test the delay with a complex template that fails."""
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {"delay": {"seconds": "{{ invalid_delay }}"}},
            {"delay": {"seconds": 5}},
            {"event": event},
        ]
    )
    script_obj = script.Script(hass, sequence)
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
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA([{"delay": {"seconds": 5}}, {"event": event}])
    script_obj = script.Script(hass, sequence)
    delay_started_flag = async_watch_for_action(script_obj, "delay")

    try:
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

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == 0


async def test_wait_template_basic(hass):
    """Test the wait template."""
    wait_alias = "wait step"
    sequence = cv.SCRIPT_SCHEMA(
        {
            "wait_template": "{{ states.switch.test.state == 'off' }}",
            "alias": wait_alias,
        }
    )
    script_obj = script.Script(hass, sequence)
    wait_started_flag = async_watch_for_action(script_obj, wait_alias)

    assert script_obj.can_cancel

    try:
        hass.states.async_set("switch.test", "on")
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
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event, "event_data": {"value": 1}},
            {"wait_template": "{{ states.switch.test.state == 'off' }}"},
            {"event": event, "event_data": {"value": 2}},
        ]
    )
    script_obj = script.Script(hass, sequence, script_mode="parallel", max_runs=2)
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    try:
        hass.states.async_set("switch.test", "on")
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
        hass.async_create_task(script_obj.async_run())
        hass.states.async_set("switch.test", "off")
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == 4
        assert events[-3].data["value"] == 1
        assert events[-2].data["value"] == 2
        assert events[-1].data["value"] == 2


async def test_cancel_wait_template(hass):
    """Test the cancelling while wait_template is present."""
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"wait_template": "{{ states.switch.test.state == 'off' }}"},
            {"event": event},
        ]
    )
    script_obj = script.Script(hass, sequence)
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    try:
        hass.states.async_set("switch.test", "on")
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
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {"wait_template": "{{ states.switch.test.state == 'on' }}"},
            {"event": event},
        ]
    )
    script_obj = script.Script(hass, sequence)

    hass.states.async_set("switch.test", "on")
    await script_obj.async_run()
    await hass.async_block_till_done()

    assert not script_obj.is_running
    assert len(events) == 2


@pytest.mark.parametrize(
    "continue_on_timeout,n_events", [(False, 0), (True, 1), (None, 1)]
)
async def test_wait_template_timeout(hass, mock_timeout, continue_on_timeout, n_events):
    """Test the wait template, halt on timeout."""
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = [
        {"wait_template": "{{ states.switch.test.state == 'off' }}", "timeout": 5},
        {"event": event},
    ]
    if continue_on_timeout is not None:
        sequence[0]["continue_on_timeout"] = continue_on_timeout
    sequence = cv.SCRIPT_SCHEMA(sequence)
    script_obj = script.Script(hass, sequence)
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run())
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 0
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == n_events


async def test_wait_template_variables(hass):
    """Test the wait template with variables."""
    sequence = cv.SCRIPT_SCHEMA({"wait_template": "{{ is_state(data, 'off') }}"})
    script_obj = script.Script(hass, sequence)
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    assert script_obj.can_cancel

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run({"data": "switch.test"}))
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
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {
                "condition": "template",
                "value_template": "{{ states.test.entity.state == 'hello' }}",
            },
            {"event": event},
        ]
    )
    script_obj = script.Script(hass, sequence)

    assert script_obj.can_cancel

    hass.states.async_set("test.entity", "hello")
    await script_obj.async_run()
    await hass.async_block_till_done()

    assert len(events) == 2

    hass.states.async_set("test.entity", "goodbye")

    await script_obj.async_run()
    await hass.async_block_till_done()

    assert len(events) == 3


@patch("homeassistant.helpers.script.condition.async_from_config")
async def test_condition_created_once(async_from_config, hass):
    """Test that the conditions do not get created multiple times."""
    sequence = cv.SCRIPT_SCHEMA(
        {
            "condition": "template",
            "value_template": '{{ states.test.entity.state == "hello" }}',
        }
    )
    script_obj = script.Script(hass, sequence, script_mode="parallel", max_runs=2)

    async_from_config.reset_mock()

    hass.states.async_set("test.entity", "hello")
    await script_obj.async_run()
    await script_obj.async_run()
    await hass.async_block_till_done()

    async_from_config.assert_called_once()
    assert len(script_obj._config_cache) == 1


async def test_condition_all_cached(hass):
    """Test that multiple conditions get cached."""
    sequence = cv.SCRIPT_SCHEMA(
        [
            {
                "condition": "template",
                "value_template": '{{ states.test.entity.state == "hello" }}',
            },
            {
                "condition": "template",
                "value_template": '{{ states.test.entity.state != "hello" }}',
            },
        ]
    )
    script_obj = script.Script(hass, sequence)

    hass.states.async_set("test.entity", "hello")
    await script_obj.async_run()
    await hass.async_block_till_done()

    assert len(script_obj._config_cache) == 2


async def test_repeat_count(hass):
    """Test repeat action w/ count option."""
    event = "test_event"
    events = async_capture_events(hass, event)
    count = 3

    sequence = cv.SCRIPT_SCHEMA(
        {
            "repeat": {
                "count": count,
                "sequence": {
                    "event": event,
                    "event_data_template": {
                        "first": "{{ repeat.first }}",
                        "index": "{{ repeat.index }}",
                        "last": "{{ repeat.last }}",
                    },
                },
            }
        }
    )
    script_obj = script.Script(hass, sequence)

    await script_obj.async_run()
    await hass.async_block_till_done()

    assert len(events) == count
    for index, event in enumerate(events):
        assert event.data.get("first") == str(index == 0)
        assert event.data.get("index") == str(index + 1)
        assert event.data.get("last") == str(index == count - 1)


@pytest.mark.parametrize("condition", ["while", "until"])
async def test_repeat_conditional(hass, condition):
    """Test repeat action w/ while option."""
    event = "test_event"
    events = async_capture_events(hass, event)
    count = 3

    sequence = {
        "repeat": {
            "sequence": [
                {
                    "event": event,
                    "event_data_template": {
                        "first": "{{ repeat.first }}",
                        "index": "{{ repeat.index }}",
                    },
                },
                {"wait_template": "{{ is_state('sensor.test', 'next') }}"},
                {"wait_template": "{{ not is_state('sensor.test', 'next') }}"},
            ],
        }
    }
    if condition == "while":
        sequence["repeat"]["while"] = {
            "condition": "template",
            "value_template": "{{ not is_state('sensor.test', 'done') }}",
        }
    else:
        sequence["repeat"]["until"] = {
            "condition": "template",
            "value_template": "{{ is_state('sensor.test', 'done') }}",
        }
    script_obj = script.Script(hass, cv.SCRIPT_SCHEMA(sequence))

    wait_started = async_watch_for_action(script_obj, "wait")
    hass.states.async_set("sensor.test", "1")

    hass.async_create_task(script_obj.async_run())
    try:
        for index in range(2, count + 1):
            await asyncio.wait_for(wait_started.wait(), 1)
            wait_started.clear()
            hass.states.async_set("sensor.test", "next")
            await asyncio.wait_for(wait_started.wait(), 1)
            wait_started.clear()
            hass.states.async_set("sensor.test", index)
        await asyncio.wait_for(wait_started.wait(), 1)
        hass.states.async_set("sensor.test", "next")
        await asyncio.wait_for(wait_started.wait(), 1)
        wait_started.clear()
        hass.states.async_set("sensor.test", "done")
        await asyncio.wait_for(hass.async_block_till_done(), 1)
    except asyncio.TimeoutError:
        await script_obj.async_stop()
        raise

    assert len(events) == count
    for index, event in enumerate(events):
        assert event.data.get("first") == str(index == 0)
        assert event.data.get("index") == str(index + 1)


async def test_last_triggered(hass):
    """Test the last_triggered."""
    event = "test_event"
    sequence = cv.SCRIPT_SCHEMA({"event": event})
    script_obj = script.Script(hass, sequence)

    assert script_obj.last_triggered is None

    time = dt_util.utcnow()
    with mock.patch("homeassistant.helpers.script.utcnow", return_value=time):
        await script_obj.async_run()
        await hass.async_block_till_done()

    assert script_obj.last_triggered == time


async def test_propagate_error_service_not_found(hass):
    """Test that a script aborts when a service is not found."""
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA([{"service": "test.script"}, {"event": event}])
    script_obj = script.Script(hass, sequence)

    with pytest.raises(exceptions.ServiceNotFound):
        await script_obj.async_run()

    assert len(events) == 0
    assert not script_obj.is_running


async def test_propagate_error_invalid_service_data(hass):
    """Test that a script aborts when we send invalid service data."""
    event = "test_event"
    events = async_capture_events(hass, event)
    calls = async_mock_service(hass, "test", "script", vol.Schema({"text": str}))
    sequence = cv.SCRIPT_SCHEMA(
        [{"service": "test.script", "data": {"text": 1}}, {"event": event}]
    )
    script_obj = script.Script(hass, sequence)

    with pytest.raises(vol.Invalid):
        await script_obj.async_run()

    assert len(events) == 0
    assert len(calls) == 0
    assert not script_obj.is_running


async def test_propagate_error_service_exception(hass):
    """Test that a script aborts when a service throws an exception."""
    event = "test_event"
    events = async_capture_events(hass, event)

    @callback
    def record_call(service):
        """Add recorded event to set."""
        raise ValueError("BROKEN")

    hass.services.async_register("test", "script", record_call)

    sequence = cv.SCRIPT_SCHEMA([{"service": "test.script"}, {"event": event}])
    script_obj = script.Script(hass, sequence)

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


@contextmanager
def does_not_raise():
    """Indicate no exception is expected."""
    yield


async def test_script_mode_single(hass, caplog):
    """Test overlapping runs with max_runs = 1."""
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event, "event_data": {"value": 1}},
            {"wait_template": "{{ states.switch.test.state == 'off' }}"},
            {"event": event, "event_data": {"value": 2}},
        ]
    )
    script_obj = script.Script(hass, sequence)
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run())
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 1
        assert events[0].data["value"] == 1

        # Start second run of script while first run is suspended in wait_template.

        await script_obj.async_run()

        assert "Already running" in caplog.text
        assert script_obj.is_running
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        hass.states.async_set("switch.test", "off")
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == 2
        assert events[1].data["value"] == 2


@pytest.mark.parametrize(
    "script_mode,messages,last_events",
    [("restart", ["Restarting"], [2]), ("parallel", [], [2, 2])],
)
async def test_script_mode_2(hass, caplog, script_mode, messages, last_events):
    """Test overlapping runs with max_runs > 1."""
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event, "event_data": {"value": 1}},
            {"wait_template": "{{ states.switch.test.state == 'off' }}"},
            {"event": event, "event_data": {"value": 2}},
        ]
    )
    logger = logging.getLogger("TEST")
    max_runs = 1 if script_mode == "restart" else 2
    script_obj = script.Script(
        hass, sequence, script_mode=script_mode, max_runs=max_runs, logger=logger
    )
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run())
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 1
        assert events[0].data["value"] == 1

        # Start second run of script while first run is suspended in wait_template.

        wait_started_flag.clear()
        hass.async_create_task(script_obj.async_run())
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 2
        assert events[1].data["value"] == 1
        assert all(
            any(
                rec.levelname == "INFO"
                and rec.name == "TEST"
                and message in rec.message
                for rec in caplog.records
            )
            for message in messages
        )
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        hass.states.async_set("switch.test", "off")
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == 2 + len(last_events)
        for idx, value in enumerate(last_events, start=2):
            assert events[idx].data["value"] == value


async def test_script_mode_queued(hass):
    """Test overlapping runs with script_mode = 'queued' & max_runs > 1."""
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event, "event_data": {"value": 1}},
            {"wait_template": "{{ states.switch.test.state == 'off' }}"},
            {"event": event, "event_data": {"value": 2}},
            {"wait_template": "{{ states.switch.test.state == 'on' }}"},
        ]
    )
    logger = logging.getLogger("TEST")
    script_obj = script.Script(
        hass, sequence, script_mode="queued", max_runs=2, logger=logger
    )
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run())
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 1
        assert events[0].data["value"] == 1

        # Start second run of script while first run is suspended in wait_template.
        # This second run should not start until the first run has finished.

        hass.async_create_task(script_obj.async_run())

        await asyncio.sleep(0)
        assert script_obj.is_running
        assert len(events) == 1

        wait_started_flag.clear()
        hass.states.async_set("switch.test", "off")
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 2
        assert events[1].data["value"] == 2

        wait_started_flag.clear()
        hass.states.async_set("switch.test", "on")
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        await asyncio.sleep(0)
        assert script_obj.is_running
        assert len(events) == 3
        assert events[2].data["value"] == 1
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        hass.states.async_set("switch.test", "off")
        await asyncio.sleep(0)
        hass.states.async_set("switch.test", "on")
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == 4
        assert events[3].data["value"] == 2


async def test_script_logging(caplog):
    """Test script logging."""
    script_obj = script.Script(None, [], "Script with % Name")
    script_obj._log("Test message with name %s", 1)

    assert "Script with % Name: Test message with name 1" in caplog.text

    script_obj = script.Script(None, [])
    script_obj._log("Test message without name %s", 2)
    assert "Test message without name 2" in caplog.text
