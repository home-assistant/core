"""The tests for the Script component."""
import asyncio
from contextlib import contextmanager
from datetime import timedelta
from functools import reduce
import logging
import operator
from types import MappingProxyType
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

from async_timeout import timeout
import pytest
import voluptuous as vol

# Otherwise can't test just this file (import order issue)
from homeassistant import exceptions
import homeassistant.components.scene as scene
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    SERVICE_TURN_ON,
)
from homeassistant.core import (
    Context,
    CoreState,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ConditionError, HomeAssistantError, ServiceNotFound
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    script,
    template,
    trace,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

ENTITY_ID = "script.test"


@pytest.fixture(autouse=True)
def prepare_tracing():
    """Prepare tracing."""
    trace.trace_get()


def compare_trigger_item(actual_trigger, expected_trigger):
    """Compare trigger data description."""
    assert actual_trigger["description"] == expected_trigger["description"]


def compare_result_item(key, actual, expected, path):
    """Compare an item in the result dict.

    Note: Unused variable 'path' is passed to get helpful errors from pytest.
    """
    if key == "wait" and (expected.get("trigger") is not None):
        assert "trigger" in actual
        expected_trigger = expected.pop("trigger")
        actual_trigger = actual.pop("trigger")
        compare_trigger_item(actual_trigger, expected_trigger)

    assert actual == expected


def assert_element(trace_element, expected_element, path):
    """Assert a trace element is as expected.

    Note: Unused variable 'path' is passed to get helpful errors from pytest.
    """
    expected_result = expected_element.get("result", {})

    # Check that every item in expected_element is present and equal in trace_element
    # The redundant set operation gives helpful errors from pytest
    assert not set(expected_result) - set(trace_element._result or {})
    for result_key, result in expected_result.items():
        compare_result_item(result_key, trace_element._result[result_key], result, path)
        assert trace_element._result[result_key] == result

    # Check for unexpected items in trace_element
    assert not set(trace_element._result or {}) - set(expected_result)

    if "error_type" in expected_element and expected_element["error_type"] is not None:
        assert isinstance(trace_element._error, expected_element["error_type"])
    else:
        assert trace_element._error is None

    # Don't check variables when script starts
    if trace_element.path == "0":
        return

    if "variables" in expected_element:
        assert expected_element["variables"] == trace_element._variables
    else:
        assert not trace_element._variables


def assert_action_trace(expected, expected_script_execution="finished"):
    """Assert a trace condition sequence is as expected."""
    action_trace = trace.trace_get(clear=False)
    script_execution = trace.script_execution_get()
    trace.trace_clear()
    expected_trace_keys = list(expected.keys())
    assert list(action_trace.keys()) == expected_trace_keys
    for trace_key_index, key in enumerate(expected_trace_keys):
        assert len(action_trace[key]) == len(expected[key])
        for index, element in enumerate(expected[key]):
            path = f"[{trace_key_index}][{index}]"
            assert_element(action_trace[key][index], element, path)

    assert script_execution == expected_script_execution


def async_watch_for_action(script_obj, message):
    """Watch for message in last_action."""
    flag = asyncio.Event()

    @callback
    def check_action():
        if script_obj.last_action and message in script_obj.last_action:
            flag.set()

    script_obj.change_listener = check_action
    assert script_obj.change_listener is check_action
    return flag


async def test_firing_event_basic(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the firing of events."""
    event = "test_event"
    context = Context()
    events = async_capture_events(hass, event)

    alias = "event step"
    sequence = cv.SCRIPT_SCHEMA(
        {"alias": alias, "event": event, "event_data": {"hello": "world"}}
    )

    script_obj = script.Script(
        hass,
        sequence,
        "Test Name",
        "test_domain",
        running_description="test script",
    )

    await script_obj.async_run(context=context)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].context is context
    assert events[0].data.get("hello") == "world"
    assert ".test_name:" in caplog.text
    assert "Test Name: Running test script" in caplog.text
    assert f"Executing step {alias}" in caplog.text

    assert_action_trace(
        {
            "0": [
                {"result": {"event": "test_event", "event_data": {"hello": "world"}}},
            ],
        }
    )


async def test_firing_event_template(hass: HomeAssistant) -> None:
    """Test the firing of events."""
    event = "test_event"
    context = Context()
    events = async_capture_events(hass, event)

    sequence = cv.SCRIPT_SCHEMA(
        {
            "event": event,
            "event_data": {
                "dict": {
                    1: "{{ is_world }}",
                    2: "{{ is_world }}{{ is_world }}",
                    3: "{{ is_world }}{{ is_world }}{{ is_world }}",
                },
                "list": ["{{ is_world }}", "{{ is_world }}{{ is_world }}"],
            },
            "event_data_template": {
                "dict2": {
                    1: "{{ is_world }}",
                    2: "{{ is_world }}{{ is_world }}",
                    3: "{{ is_world }}{{ is_world }}{{ is_world }}",
                },
                "list2": ["{{ is_world }}", "{{ is_world }}{{ is_world }}"],
            },
        }
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(MappingProxyType({"is_world": "yes"}), context=context)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].context is context
    assert events[0].data == {
        "dict": {1: "yes", 2: "yesyes", 3: "yesyesyes"},
        "list": ["yes", "yesyes"],
        "dict2": {1: "yes", 2: "yesyes", 3: "yesyesyes"},
        "list2": ["yes", "yesyes"],
    }

    assert_action_trace(
        {
            "0": [
                {
                    "result": {
                        "event": "test_event",
                        "event_data": {
                            "dict": {1: "yes", 2: "yesyes", 3: "yesyesyes"},
                            "dict2": {1: "yes", 2: "yesyes", 3: "yesyesyes"},
                            "list": ["yes", "yesyes"],
                            "list2": ["yes", "yesyes"],
                        },
                    }
                }
            ],
        }
    )


async def test_calling_service_basic(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the calling of a service."""
    context = Context()
    calls = async_mock_service(hass, "test", "script")

    alias = "service step"
    sequence = cv.SCRIPT_SCHEMA(
        {"alias": alias, "service": "test.script", "data": {"hello": "world"}}
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=context)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].context is context
    assert calls[0].data.get("hello") == "world"
    assert f"Executing step {alias}" in caplog.text

    assert_action_trace(
        {
            "0": [
                {
                    "result": {
                        "params": {
                            "domain": "test",
                            "service": "script",
                            "service_data": {"hello": "world"},
                            "target": {},
                        },
                        "running_script": False,
                    }
                }
            ],
        }
    )


async def test_calling_service_template(hass: HomeAssistant) -> None:
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
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(MappingProxyType({"is_world": "yes"}), context=context)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].context is context
    assert calls[0].data.get("hello") == "world"

    assert_action_trace(
        {
            "0": [
                {
                    "result": {
                        "params": {
                            "domain": "test",
                            "service": "script",
                            "service_data": {"hello": "world"},
                            "target": {},
                        },
                        "running_script": False,
                    }
                }
            ],
        }
    )


async def test_calling_service_response_data(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the calling of a service with response data."""
    context = Context()

    def mock_service(call: ServiceCall) -> ServiceResponse:
        """Mock service call."""
        if call.return_response:
            return {"data": "value-12345"}
        return None

    hass.services.async_register(
        "test", "script", mock_service, supports_response=SupportsResponse.OPTIONAL
    )
    sequence = cv.SCRIPT_SCHEMA(
        [
            {
                "alias": "service step1",
                "service": "test.script",
                # Store the result of the service call as a variable
                "response_variable": "my_response",
            },
            {
                "alias": "service step2",
                "service": "test.script",
                "data_template": {
                    # Result of previous service call
                    "key": "{{ my_response.data }}"
                },
            },
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=context)
    await hass.async_block_till_done()

    assert "Executing step service step1" in caplog.text
    assert "Executing step service step2" in caplog.text

    assert_action_trace(
        {
            "0": [
                {
                    "result": {
                        "params": {
                            "domain": "test",
                            "service": "script",
                            "service_data": {},
                            "target": {},
                        },
                        "running_script": False,
                    }
                }
            ],
            "1": [
                {
                    "result": {
                        "params": {
                            "domain": "test",
                            "service": "script",
                            "service_data": {"key": "value-12345"},
                            "target": {},
                        },
                        "running_script": False,
                    },
                    "variables": {
                        "my_response": {"data": "value-12345"},
                    },
                }
            ],
        }
    )


@pytest.mark.parametrize(
    ("supports_response", "params", "expected_error"),
    [
        (
            SupportsResponse.NONE,
            {"response_variable": "foo"},
            "does not support 'response_variable'",
        ),
        (SupportsResponse.ONLY, {}, "requires 'response_variable'"),
    ],
)
async def test_service_response_data_errors(
    hass: HomeAssistant,
    supports_response: SupportsResponse,
    params: dict[str, str],
    expected_error: str,
) -> None:
    """Test the calling of a service with response data error cases."""
    context = Context()

    def mock_service(call: ServiceCall) -> ServiceResponse:
        """Mock service call."""
        raise ValueError("Never invoked")

    hass.services.async_register(
        "test", "script", mock_service, supports_response=supports_response
    )

    sequence = cv.SCRIPT_SCHEMA(
        [
            {
                "alias": "service step1",
                "service": "test.script",
                **params,
            },
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    with pytest.raises(vol.Invalid, match=expected_error):
        await script_obj.async_run(context=context)
        await hass.async_block_till_done()


async def test_data_template_with_templated_key(hass: HomeAssistant) -> None:
    """Test the calling of a service with a data_template with a templated key."""
    context = Context()
    calls = async_mock_service(hass, "test", "script")

    sequence = cv.SCRIPT_SCHEMA(
        {"service": "test.script", "data_template": {"{{ hello_var }}": "world"}}
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(
        MappingProxyType({"hello_var": "hello"}), context=context
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].context is context
    assert calls[0].data.get("hello") == "world"

    assert_action_trace(
        {
            "0": [
                {
                    "result": {
                        "params": {
                            "domain": "test",
                            "service": "script",
                            "service_data": {"hello": "world"},
                            "target": {},
                        },
                        "running_script": False,
                    }
                }
            ],
        }
    )


async def test_multiple_runs_no_wait(hass: HomeAssistant) -> None:
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
        unsub = hass.bus.async_listen(str(listen), service_done_cb)
        hass.bus.async_fire(str(fire))
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
    script_obj = script.Script(
        hass, sequence, "Test Name", "test_domain", script_mode="parallel", max_runs=2
    )

    # Start script twice in such a way that second run will be started while first run
    # is in the middle of the first service call.

    unsub = hass.bus.async_listen("1", heard_event_cb)
    logger.debug("starting 1st script")
    hass.async_create_task(
        script_obj.async_run(
            MappingProxyType(
                {"fire1": "1", "listen1": "2", "fire2": "3", "listen2": "4"}
            ),
            Context(),
        )
    )
    await asyncio.wait_for(heard_event.wait(), 1)
    unsub()

    logger.debug("starting 2nd script")
    await script_obj.async_run(
        MappingProxyType({"fire1": "2", "listen1": "3", "fire2": "4", "listen2": "4"}),
        Context(),
    )
    await hass.async_block_till_done()

    assert len(calls) == 4


async def test_activating_scene(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the activation of a scene."""
    context = Context()
    calls = async_mock_service(hass, scene.DOMAIN, SERVICE_TURN_ON)

    alias = "scene step"
    sequence = cv.SCRIPT_SCHEMA({"alias": alias, "scene": "scene.hello"})
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=context)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].context is context
    assert calls[0].data.get(ATTR_ENTITY_ID) == "scene.hello"
    assert f"Executing step {alias}" in caplog.text

    assert_action_trace(
        {
            "0": [{"result": {"scene": "scene.hello"}}],
        }
    )


@pytest.mark.parametrize("count", [1, 3])
async def test_stop_no_wait(hass: HomeAssistant, count) -> None:
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
    script_obj = script.Script(
        hass,
        sequence,
        "Test Name",
        "test_domain",
        script_mode="parallel",
        max_runs=count,
    )

    # Get script started specified number of times and wait until the test.script
    # service has started for each run.
    tasks = []
    for _ in range(count):
        hass.async_create_task(script_obj.async_run(context=Context()))
        tasks.append(hass.async_create_task(service_started_sem.acquire()))
    await asyncio.wait_for(asyncio.gather(*tasks), 1)

    # Can't assert just yet because we haven't verified stopping works yet.
    # If assert fails we can hang test if async_stop doesn't work.
    script_was_running = script_obj.is_running
    were_no_events = len(events) == 0

    # Begin the process of stopping the script (which should stop all runs), and then
    # let the service calls complete.
    hass.async_create_task(script_obj.async_stop())
    finish_service_event.set()

    await hass.async_block_till_done()

    assert script_was_running
    assert were_no_events
    assert not script_obj.is_running
    assert len(events) == 0


async def test_delay_basic(hass: HomeAssistant) -> None:
    """Test the delay."""
    delay_alias = "delay step"
    sequence = cv.SCRIPT_SCHEMA({"delay": {"seconds": 5}, "alias": delay_alias})
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    delay_started_flag = async_watch_for_action(script_obj, delay_alias)

    try:
        hass.async_create_task(script_obj.async_run(context=Context()))
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

    assert_action_trace(
        {
            "0": [{"result": {"delay": 5.0, "done": True}}],
        }
    )


async def test_multiple_runs_delay(hass: HomeAssistant) -> None:
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
    script_obj = script.Script(
        hass, sequence, "Test Name", "test_domain", script_mode="parallel", max_runs=2
    )
    delay_started_flag = async_watch_for_action(script_obj, "delay")

    try:
        hass.async_create_task(script_obj.async_run(context=Context()))
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
        hass.async_create_task(script_obj.async_run(context=Context()))
        await asyncio.wait_for(delay_started_flag.wait(), 1)
        async_fire_time_changed(hass, dt_util.utcnow() + delay)
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == 4
        assert events[-3].data["value"] == 1
        assert events[-2].data["value"] == 2
        assert events[-1].data["value"] == 2


async def test_delay_template_ok(hass: HomeAssistant) -> None:
    """Test the delay as a template."""
    sequence = cv.SCRIPT_SCHEMA({"delay": "00:00:{{ 5 }}"})
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    delay_started_flag = async_watch_for_action(script_obj, "delay")

    try:
        hass.async_create_task(script_obj.async_run(context=Context()))
        await asyncio.wait_for(delay_started_flag.wait(), 1)

        assert script_obj.is_running
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done()

        assert not script_obj.is_running

    assert_action_trace(
        {
            "0": [{"result": {"delay": 5.0, "done": True}}],
        }
    )


async def test_delay_template_invalid(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
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
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    start_idx = len(caplog.records)

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert any(
        rec.levelname == "ERROR" and "Error rendering" in rec.message
        for rec in caplog.records[start_idx:]
    )

    assert not script_obj.is_running
    assert len(events) == 1

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"error_type": vol.MultipleInvalid}],
        },
        expected_script_execution="aborted",
    )


async def test_delay_template_complex_ok(hass: HomeAssistant) -> None:
    """Test the delay with a working complex template."""
    sequence = cv.SCRIPT_SCHEMA({"delay": {"seconds": "{{ 5 }}"}})
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    delay_started_flag = async_watch_for_action(script_obj, "delay")

    try:
        hass.async_create_task(script_obj.async_run(context=Context()))
        await asyncio.wait_for(delay_started_flag.wait(), 1)
        assert script_obj.is_running
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done()

        assert not script_obj.is_running

    assert_action_trace(
        {
            "0": [{"result": {"delay": 5.0, "done": True}}],
        }
    )


async def test_delay_template_complex_invalid(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
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
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    start_idx = len(caplog.records)

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert any(
        rec.levelname == "ERROR" and "Error rendering" in rec.message
        for rec in caplog.records[start_idx:]
    )

    assert not script_obj.is_running
    assert len(events) == 1

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"error_type": vol.MultipleInvalid}],
        },
        expected_script_execution="aborted",
    )


async def test_cancel_delay(hass: HomeAssistant) -> None:
    """Test the cancelling while the delay is present."""
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA([{"delay": {"seconds": 5}}, {"event": event}])
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    delay_started_flag = async_watch_for_action(script_obj, "delay")

    try:
        hass.async_create_task(script_obj.async_run(context=Context()))
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

    assert_action_trace(
        {
            "0": [{"result": {"delay": 5.0, "done": False}}],
        },
        expected_script_execution="cancelled",
    )


@pytest.mark.parametrize("action_type", ["template", "trigger"])
async def test_wait_basic(hass: HomeAssistant, action_type) -> None:
    """Test wait actions."""
    wait_alias = "wait step"
    action = {"alias": wait_alias}
    if action_type == "template":
        action["wait_template"] = "{{ states.switch.test.state == 'off' }}"
    else:
        action["wait_for_trigger"] = {
            "platform": "state",
            "entity_id": "switch.test",
            "to": "off",
        }
    sequence = cv.SCRIPT_SCHEMA(action)
    sequence = await script.async_validate_actions_config(hass, sequence)
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    wait_started_flag = async_watch_for_action(script_obj, wait_alias)

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run(context=Context()))
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

    if action_type == "template":
        assert_action_trace(
            {
                "0": [{"result": {"wait": {"completed": True, "remaining": None}}}],
            }
        )
    else:
        assert_action_trace(
            {
                "0": [
                    {
                        "result": {
                            "wait": {
                                "trigger": {"description": "state of switch.test"},
                                "remaining": None,
                            }
                        }
                    }
                ],
            }
        )


async def test_wait_for_trigger_variables(hass: HomeAssistant) -> None:
    """Test variables are passed to wait_for_trigger action."""
    context = Context()
    wait_alias = "wait step"
    actions = [
        {
            "alias": "variables",
            "variables": {"state": "off"},
        },
        {
            "alias": wait_alias,
            "wait_for_trigger": {
                "platform": "template",
                "value_template": "{{ states.switch.test.state == state }}",
            },
        },
    ]
    sequence = cv.SCRIPT_SCHEMA(actions)
    sequence = await script.async_validate_actions_config(hass, sequence)
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    wait_started_flag = async_watch_for_action(script_obj, wait_alias)

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run(context=context))
        await asyncio.wait_for(wait_started_flag.wait(), 1)
        assert script_obj.is_running
        assert script_obj.last_action == wait_alias
        hass.states.async_set("switch.test", "off")
        await hass.async_block_till_done()
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        assert not script_obj.is_running
        assert script_obj.last_action is None


@pytest.mark.parametrize("action_type", ["template", "trigger"])
async def test_wait_basic_times_out(hass: HomeAssistant, action_type) -> None:
    """Test wait actions times out when the action does not happen."""
    wait_alias = "wait step"
    action = {"alias": wait_alias}
    if action_type == "template":
        action["wait_template"] = "{{ states.switch.test.state == 'off' }}"
    else:
        action["wait_for_trigger"] = {
            "platform": "state",
            "entity_id": "switch.test",
            "to": "off",
        }
    sequence = cv.SCRIPT_SCHEMA(action)
    sequence = await script.async_validate_actions_config(hass, sequence)
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    wait_started_flag = async_watch_for_action(script_obj, wait_alias)
    timed_out = False

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run(context=Context()))
        await asyncio.wait_for(wait_started_flag.wait(), 1)
        assert script_obj.is_running
        assert script_obj.last_action == wait_alias
        hass.states.async_set("switch.test", "not_on")

        async with timeout(0.1):
            await hass.async_block_till_done()
    except asyncio.TimeoutError:
        timed_out = True
        await script_obj.async_stop()

    assert timed_out

    if action_type == "template":
        assert_action_trace(
            {
                "0": [{"result": {"wait": {"completed": False, "remaining": None}}}],
            }
        )
    else:
        assert_action_trace(
            {
                "0": [{"result": {"wait": {"trigger": None, "remaining": None}}}],
            }
        )


@pytest.mark.parametrize("action_type", ["template", "trigger"])
async def test_multiple_runs_wait(hass: HomeAssistant, action_type) -> None:
    """Test multiple runs with wait in script."""
    event = "test_event"
    events = async_capture_events(hass, event)
    if action_type == "template":
        action = {"wait_template": "{{ states.switch.test.state == 'off' }}"}
    else:
        action = {
            "wait_for_trigger": {
                "platform": "state",
                "entity_id": "switch.test",
                "to": "off",
            }
        }
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event, "event_data": {"value": 1}},
            action,
            {"event": event, "event_data": {"value": 2}},
        ]
    )
    sequence = await script.async_validate_actions_config(hass, sequence)
    script_obj = script.Script(
        hass, sequence, "Test Name", "test_domain", script_mode="parallel", max_runs=2
    )
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run(context=Context()))
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 1
        assert events[-1].data["value"] == 1

        # Start second run of script while first run is in wait_template.
        wait_started_flag.clear()
        hass.async_create_task(script_obj.async_run())
        await asyncio.wait_for(wait_started_flag.wait(), 1)
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        hass.states.async_set("switch.test", "off")
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == 4
        assert events[-3].data["value"] == 1
        assert events[-2].data["value"] == 2
        assert events[-1].data["value"] == 2


@pytest.mark.parametrize("action_type", ["template", "trigger"])
async def test_cancel_wait(hass: HomeAssistant, action_type) -> None:
    """Test the cancelling while wait is present."""
    event = "test_event"
    events = async_capture_events(hass, event)
    if action_type == "template":
        action = {"wait_template": "{{ states.switch.test.state == 'off' }}"}
    else:
        action = {
            "wait_for_trigger": {
                "platform": "state",
                "entity_id": "switch.test",
                "to": "off",
            }
        }
    sequence = cv.SCRIPT_SCHEMA([action, {"event": event}])
    sequence = await script.async_validate_actions_config(hass, sequence)
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run(context=Context()))
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

    if action_type == "template":
        assert_action_trace(
            {
                "0": [{"result": {"wait": {"completed": False, "remaining": None}}}],
            },
            expected_script_execution="cancelled",
        )
    else:
        assert_action_trace(
            {
                "0": [{"result": {"wait": {"trigger": None, "remaining": None}}}],
            },
            expected_script_execution="cancelled",
        )


async def test_wait_template_not_schedule(hass: HomeAssistant) -> None:
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
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    hass.states.async_set("switch.test", "on")
    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert not script_obj.is_running
    assert len(events) == 2

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"result": {"wait": {"completed": True, "remaining": None}}}],
            "2": [
                {
                    "result": {"event": "test_event", "event_data": {}},
                    "variables": {"wait": {"completed": True, "remaining": None}},
                }
            ],
        }
    )


@pytest.mark.parametrize(
    "timeout_param", [5, "{{ 5 }}", {"seconds": 5}, {"seconds": "{{ 5 }}"}]
)
@pytest.mark.parametrize("action_type", ["template", "trigger"])
async def test_wait_timeout(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, timeout_param, action_type
) -> None:
    """Test the wait timeout option."""
    event = "test_event"
    events = async_capture_events(hass, event)
    if action_type == "template":
        action = {"wait_template": "{{ states.switch.test.state == 'off' }}"}
    else:
        action = {
            "wait_for_trigger": {
                "platform": "state",
                "entity_id": "switch.test",
                "to": "off",
            }
        }
    action["timeout"] = timeout_param
    action["continue_on_timeout"] = True
    sequence = cv.SCRIPT_SCHEMA([action, {"event": event}])
    sequence = await script.async_validate_actions_config(hass, sequence)
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run(context=Context()))
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 0
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        cur_time = dt_util.utcnow()
        async_fire_time_changed(hass, cur_time + timedelta(seconds=4))
        await asyncio.sleep(0)

        assert len(events) == 0

        async_fire_time_changed(hass, cur_time + timedelta(seconds=5))
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == 1
        assert "(timeout: 0:00:05)" in caplog.text

    if action_type == "template":
        variable_wait = {"wait": {"completed": False, "remaining": 0.0}}
    else:
        variable_wait = {"wait": {"trigger": None, "remaining": 0.0}}
    expected_trace = {
        "0": [{"result": variable_wait}],
        "1": [
            {
                "result": {"event": "test_event", "event_data": {}},
                "variables": variable_wait,
            }
        ],
    }
    assert_action_trace(expected_trace)


@pytest.mark.parametrize(
    ("continue_on_timeout", "n_events"), [(False, 0), (True, 1), (None, 1)]
)
@pytest.mark.parametrize("action_type", ["template", "trigger"])
async def test_wait_continue_on_timeout(
    hass: HomeAssistant, continue_on_timeout, n_events, action_type
) -> None:
    """Test the wait continue_on_timeout option."""
    event = "test_event"
    events = async_capture_events(hass, event)
    if action_type == "template":
        action = {"wait_template": "{{ states.switch.test.state == 'off' }}"}
    else:
        action = {
            "wait_for_trigger": {
                "platform": "state",
                "entity_id": "switch.test",
                "to": "off",
            }
        }
    action["timeout"] = 5
    if continue_on_timeout is not None:
        action["continue_on_timeout"] = continue_on_timeout
    sequence = cv.SCRIPT_SCHEMA([action, {"event": event}])
    sequence = await script.async_validate_actions_config(hass, sequence)
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run(context=Context()))
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

    if action_type == "template":
        variable_wait = {"wait": {"completed": False, "remaining": 0.0}}
    else:
        variable_wait = {"wait": {"trigger": None, "remaining": 0.0}}
    expected_trace = {
        "0": [{"result": variable_wait}],
    }
    if continue_on_timeout is False:
        expected_trace["0"][0]["result"]["timeout"] = True
        expected_trace["0"][0]["error_type"] = asyncio.TimeoutError
        expected_script_execution = "aborted"
    else:
        expected_trace["1"] = [
            {
                "result": {"event": "test_event", "event_data": {}},
                "variables": variable_wait,
            }
        ]
        expected_script_execution = "finished"
    assert_action_trace(expected_trace, expected_script_execution)


async def test_wait_template_variables_in(hass: HomeAssistant) -> None:
    """Test the wait template with input variables."""
    sequence = cv.SCRIPT_SCHEMA({"wait_template": "{{ is_state(data, 'off') }}"})
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(
            script_obj.async_run(MappingProxyType({"data": "switch.test"}), Context())
        )
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        hass.states.async_set("switch.test", "off")
        await hass.async_block_till_done()

        assert not script_obj.is_running

    assert_action_trace(
        {
            "0": [{"result": {"wait": {"completed": True, "remaining": None}}}],
        }
    )


async def test_wait_template_with_utcnow(hass: HomeAssistant) -> None:
    """Test the wait template with utcnow."""
    sequence = cv.SCRIPT_SCHEMA({"wait_template": "{{ utcnow().hour == 12 }}"})
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    wait_started_flag = async_watch_for_action(script_obj, "wait")
    start_time = dt_util.utcnow().replace(minute=1) + timedelta(hours=48)

    try:
        non_matching_time = start_time.replace(hour=3)
        with patch("homeassistant.util.dt.utcnow", return_value=non_matching_time):
            hass.async_create_task(script_obj.async_run(context=Context()))
            await asyncio.wait_for(wait_started_flag.wait(), 1)
            assert script_obj.is_running

        match_time = start_time.replace(hour=12)
        with patch("homeassistant.util.dt.utcnow", return_value=match_time):
            async_fire_time_changed(hass, match_time)
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        await hass.async_block_till_done()
        assert not script_obj.is_running

    assert_action_trace(
        {
            "0": [{"result": {"wait": {"completed": True, "remaining": None}}}],
        }
    )


async def test_wait_template_with_utcnow_no_match(hass: HomeAssistant) -> None:
    """Test the wait template with utcnow that does not match."""
    sequence = cv.SCRIPT_SCHEMA({"wait_template": "{{ utcnow().hour == 12 }}"})
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    wait_started_flag = async_watch_for_action(script_obj, "wait")
    start_time = dt_util.utcnow().replace(minute=1) + timedelta(hours=48)
    timed_out = False

    try:
        non_matching_time = start_time.replace(hour=3)
        with patch("homeassistant.util.dt.utcnow", return_value=non_matching_time):
            hass.async_create_task(script_obj.async_run(context=Context()))
            await asyncio.wait_for(wait_started_flag.wait(), 1)
            assert script_obj.is_running

        second_non_matching_time = start_time.replace(hour=4)
        with patch(
            "homeassistant.util.dt.utcnow", return_value=second_non_matching_time
        ):
            async_fire_time_changed(hass, second_non_matching_time)

        async with timeout(0.1):
            await hass.async_block_till_done()
    except asyncio.TimeoutError:
        timed_out = True
        await script_obj.async_stop()

    assert timed_out

    assert_action_trace(
        {
            "0": [{"result": {"wait": {"completed": False, "remaining": None}}}],
        }
    )


@pytest.mark.parametrize("mode", ["no_timeout", "timeout_finish", "timeout_not_finish"])
@pytest.mark.parametrize("action_type", ["template", "trigger"])
async def test_wait_variables_out(hass: HomeAssistant, mode, action_type) -> None:
    """Test the wait output variable."""
    event = "test_event"
    events = async_capture_events(hass, event)
    if action_type == "template":
        action = {"wait_template": "{{ states.switch.test.state == 'off' }}"}
        event_key = "completed"
    else:
        action = {
            "wait_for_trigger": {
                "platform": "state",
                "entity_id": "switch.test",
                "to": "off",
            }
        }
        event_key = "trigger"
    if mode != "no_timeout":
        action["timeout"] = 5
        action["continue_on_timeout"] = True
    sequence = [
        action,
        {
            "event": event,
            "event_data_template": {
                event_key: f"{{{{ wait.{event_key} }}}}",
                "remaining": "{{ wait.remaining }}",
            },
        },
    ]
    sequence = cv.SCRIPT_SCHEMA(sequence)
    sequence = await script.async_validate_actions_config(hass, sequence)
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run(context=Context()))
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 0
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        if mode == "timeout_not_finish":
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
        else:
            hass.states.async_set("switch.test", "off")
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert len(events) == 1
        if action_type == "template":
            assert events[0].data["completed"] == (mode != "timeout_not_finish")
        elif mode != "timeout_not_finish":
            assert "'to_state': <state switch.test=off" in events[0].data["trigger"]
        else:
            assert events[0].data["trigger"] is None
        remaining = events[0].data["remaining"]
        if mode == "no_timeout":
            assert remaining is None
        elif mode == "timeout_finish":
            assert 0.0 < float(remaining) < 5
        else:
            assert float(remaining) == 0.0


async def test_wait_for_trigger_bad(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test bad wait_for_trigger."""
    sequence = cv.SCRIPT_SCHEMA(
        {"wait_for_trigger": {"platform": "state", "entity_id": "sensor.abc"}}
    )
    sequence = await script.async_validate_actions_config(hass, sequence)
    script_obj = script.Script(
        hass,
        sequence,
        "Test Name",
        "test_domain",
    )

    async def async_attach_trigger_mock(*args, **kwargs):
        return None

    with mock.patch(
        "homeassistant.components.homeassistant.triggers.state.async_attach_trigger",
        wraps=async_attach_trigger_mock,
    ):
        hass.async_create_task(script_obj.async_run())
        await hass.async_block_till_done()

    assert "Unknown error while setting up trigger" in caplog.text

    assert_action_trace(
        {
            "0": [{"result": {"wait": {"trigger": None, "remaining": None}}}],
        }
    )


async def test_wait_for_trigger_generated_exception(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test bad wait_for_trigger."""
    sequence = cv.SCRIPT_SCHEMA(
        {"wait_for_trigger": {"platform": "state", "entity_id": "sensor.abc"}}
    )
    sequence = await script.async_validate_actions_config(hass, sequence)
    script_obj = script.Script(
        hass,
        sequence,
        "Test Name",
        "test_domain",
    )

    async def async_attach_trigger_mock(*args, **kwargs):
        raise ValueError("something bad")

    with mock.patch(
        "homeassistant.components.homeassistant.triggers.state.async_attach_trigger",
        wraps=async_attach_trigger_mock,
    ):
        hass.async_create_task(script_obj.async_run())
        await hass.async_block_till_done()

    assert "Error setting up trigger" in caplog.text
    assert "ValueError" in caplog.text
    assert "something bad" in caplog.text

    assert_action_trace(
        {
            "0": [{"result": {"wait": {"trigger": None, "remaining": None}}}],
        }
    )


async def test_condition_warning(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test warning on condition."""
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {
                "condition": "numeric_state",
                "entity_id": "test.entity",
                "above": 0,
            },
            {"event": event},
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    caplog.clear()
    caplog.set_level(logging.WARNING)

    hass.states.async_set("test.entity", "string")
    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert len(caplog.record_tuples) == 1
    assert caplog.record_tuples[0][1] == logging.WARNING

    assert len(events) == 1

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"result": {"result": False}}],
            "1/entity_id/0": [{"error_type": ConditionError}],
        },
        expected_script_execution="aborted",
    )


async def test_condition_basic(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if we can use conditions in a script."""
    event = "test_event"
    events = async_capture_events(hass, event)
    alias = "condition step"
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {
                "alias": alias,
                "condition": "template",
                "value_template": "{{ states.test.entity.state == 'hello' }}",
            },
            {"event": event},
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    hass.states.async_set("test.entity", "hello")
    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert f"Test condition {alias}: True" in caplog.text
    caplog.clear()
    assert len(events) == 2

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"result": {"entities": ["test.entity"], "result": True}}],
            "2": [{"result": {"event": "test_event", "event_data": {}}}],
        }
    )

    hass.states.async_set("test.entity", "goodbye")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert f"Test condition {alias}: False" in caplog.text
    assert len(events) == 3

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [
                {
                    "result": {"entities": ["test.entity"], "result": False},
                }
            ],
        },
        expected_script_execution="aborted",
    )


async def test_condition_subscript(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test failing conditions in a subscript don't stop the parent script."""
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {
                "repeat": {
                    "until": "{{ 1 == 1 }}",
                    "sequence": [
                        {"condition": "{{ 1 == 2 }}"},
                    ],
                }
            },
            {"event": event},
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    hass.states.async_set("test.entity", "hello")
    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    caplog.clear()
    assert len(events) == 2

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"result": {}}],
            "1/repeat/sequence/0": [
                {
                    "variables": {"repeat": {"first": True, "index": 1}},
                    "result": {"entities": [], "result": False},
                }
            ],
            "1/repeat": [
                {
                    "variables": {"repeat": {"first": True, "index": 1}},
                    "result": {"result": True},
                }
            ],
            "1/repeat/until/0": [{"result": {"entities": [], "result": True}}],
            "2": [{"result": {"event": "test_event", "event_data": {}}}],
        }
    )


async def test_and_default_condition(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a list of conditions evaluates as AND."""
    alias = "condition step"
    sequence = cv.SCRIPT_SCHEMA(
        [
            {
                "alias": alias,
                "condition": [
                    {
                        "condition": "template",
                        "value_template": "{{ states.test.entity.state == 'hello' }}",
                    },
                    {
                        "condition": "numeric_state",
                        "entity_id": "sensor.temperature",
                        "below": 110,
                    },
                ],
            },
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    hass.states.async_set("sensor.temperature", 100)
    hass.states.async_set("test.entity", "hello")
    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()
    assert f"Test condition {alias}: True" in caplog.text
    caplog.clear()

    hass.states.async_set("sensor.temperature", 120)
    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()
    assert f"Test condition {alias}: False" in caplog.text


async def test_shorthand_template_condition(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if we can use shorthand template conditions in a script."""
    event = "test_event"
    events = async_capture_events(hass, event)
    alias = "condition step"
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {
                "alias": alias,
                "condition": "{{ states.test.entity.state == 'hello' }}",
            },
            {"event": event},
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    hass.states.async_set("test.entity", "hello")
    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert f"Test condition {alias}: True" in caplog.text
    caplog.clear()
    assert len(events) == 2

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"result": {"entities": ["test.entity"], "result": True}}],
            "2": [{"result": {"event": "test_event", "event_data": {}}}],
        }
    )

    hass.states.async_set("test.entity", "goodbye")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert f"Test condition {alias}: False" in caplog.text
    assert len(events) == 3

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [
                {
                    "result": {"entities": ["test.entity"], "result": False},
                }
            ],
        },
        expected_script_execution="aborted",
    )


async def test_condition_validation(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if we can use conditions which validate late in a script."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        "test", "hue", "1234", suggested_object_id="entity"
    )
    assert entry.entity_id == "test.entity"
    event = "test_event"
    events = async_capture_events(hass, event)
    alias = "condition step"
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {
                "alias": alias,
                "condition": "state",
                "entity_id": entry.id,
                "state": "hello",
            },
            {"event": event},
        ]
    )
    sequence = await script.async_validate_actions_config(hass, sequence)
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    hass.states.async_set("test.entity", "hello")
    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert f"Test condition {alias}: True" in caplog.text
    caplog.clear()
    assert len(events) == 2

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"result": {"result": True}}],
            "1/entity_id/0": [
                {"result": {"result": True, "state": "hello", "wanted_state": "hello"}}
            ],
            "2": [{"result": {"event": "test_event", "event_data": {}}}],
        }
    )

    hass.states.async_set("test.entity", "goodbye")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert f"Test condition {alias}: False" in caplog.text
    assert len(events) == 3

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [
                {
                    "result": {"result": False},
                }
            ],
            "1/entity_id/0": [
                {
                    "result": {
                        "result": False,
                        "state": "goodbye",
                        "wanted_state": "hello",
                    }
                }
            ],
        },
        expected_script_execution="aborted",
    )


@patch("homeassistant.helpers.script.condition.async_from_config")
async def test_condition_created_once(async_from_config, hass: HomeAssistant) -> None:
    """Test that the conditions do not get created multiple times."""
    sequence = cv.SCRIPT_SCHEMA(
        {
            "condition": "template",
            "value_template": '{{ states.test.entity.state == "hello" }}',
        }
    )
    script_obj = script.Script(
        hass, sequence, "Test Name", "test_domain", script_mode="parallel", max_runs=2
    )

    async_from_config.reset_mock()
    async_from_config.return_value = MagicMock()

    hass.states.async_set("test.entity", "hello")
    await script_obj.async_run(context=Context())
    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    async_from_config.assert_called_once()
    assert len(script_obj._config_cache) == 1


async def test_condition_all_cached(hass: HomeAssistant) -> None:
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
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    hass.states.async_set("test.entity", "hello")
    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert len(script_obj._config_cache) == 2


@pytest.mark.parametrize("count", [3, script.ACTION_TRACE_NODE_MAX_LEN * 2])
async def test_repeat_count(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, count
) -> None:
    """Test repeat action w/ count option."""
    event = "test_event"
    events = async_capture_events(hass, event)

    alias = "condition step"
    sequence = cv.SCRIPT_SCHEMA(
        {
            "alias": alias,
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
            },
        }
    )

    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert len(events) == count
    for index, event in enumerate(events):
        assert event.data.get("first") == (index == 0)
        assert event.data.get("index") == index + 1
        assert event.data.get("last") == (index == count - 1)
    assert caplog.text.count(f"Repeating {alias}") == count
    first_index = max(1, count - script.ACTION_TRACE_NODE_MAX_LEN + 1)
    last_index = count + 1
    assert_action_trace(
        {
            "0": [{}],
            "0/repeat/sequence/0": [
                {
                    "result": {
                        "event": "test_event",
                        "event_data": {
                            "first": index == 1,
                            "index": index,
                            "last": index == count,
                        },
                    },
                    "variables": {
                        "repeat": {
                            "first": index == 1,
                            "index": index,
                            "last": index == count,
                        }
                    },
                }
                for index in range(first_index, last_index)
            ],
        }
    )


async def test_repeat_count_0(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test repeat action w/ count option."""
    event = "test_event"
    events = async_capture_events(hass, event)
    count = 0

    alias = "condition step"
    sequence = cv.SCRIPT_SCHEMA(
        {
            "alias": alias,
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
            },
        }
    )

    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert len(events) == count
    assert caplog.text.count(f"Repeating {alias}") == count
    assert_action_trace(
        {
            "0": [{}],
        }
    )


async def test_repeat_for_each(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test repeat action using for each."""
    events = async_capture_events(hass, "test_event")
    sequence = cv.SCRIPT_SCHEMA(
        {
            "alias": "For each!",
            "repeat": {
                "for_each": ["one", "two", "{{ 'thr' + 'ee' }}"],
                "sequence": {
                    "event": "test_event",
                    "event_data": {
                        "first": "{{ repeat.first }}",
                        "index": "{{ repeat.index }}",
                        "last": "{{ repeat.last }}",
                        "item": "{{ repeat.item }}",
                    },
                },
            },
        }
    )

    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert len(events) == 3
    assert "Repeating For each!: Iteration 1 of 3 with item: 'one'" in caplog.text
    assert "Repeating For each!: Iteration 2 of 3 with item: 'two'" in caplog.text
    assert "Repeating For each!: Iteration 3 of 3 with item: 'three'" in caplog.text

    assert_action_trace(
        {
            "0": [{}],
            "0/repeat/sequence/0": [
                {
                    "result": {
                        "event": "test_event",
                        "event_data": {
                            "first": True,
                            "index": 1,
                            "last": False,
                            "item": "one",
                        },
                    },
                    "variables": {
                        "repeat": {
                            "first": True,
                            "index": 1,
                            "last": False,
                            "item": "one",
                        }
                    },
                },
                {
                    "result": {
                        "event": "test_event",
                        "event_data": {
                            "first": False,
                            "index": 2,
                            "last": False,
                            "item": "two",
                        },
                    },
                    "variables": {
                        "repeat": {
                            "first": False,
                            "index": 2,
                            "last": False,
                            "item": "two",
                        }
                    },
                },
                {
                    "result": {
                        "event": "test_event",
                        "event_data": {
                            "first": False,
                            "index": 3,
                            "last": True,
                            "item": "three",
                        },
                    },
                    "variables": {
                        "repeat": {
                            "first": False,
                            "index": 3,
                            "last": True,
                            "item": "three",
                        }
                    },
                },
            ],
        }
    )


async def test_repeat_for_each_template(hass: HomeAssistant) -> None:
    """Test repeat action using for each template."""
    events = async_capture_events(hass, "test_event")
    sequence = cv.SCRIPT_SCHEMA(
        {
            "alias": "",
            "repeat": {
                "for_each": (
                    "{% set var = ['light.bulb_one', 'light.bulb_two'] %} {{ var }}"
                ),
                "sequence": {
                    "event": "test_event",
                },
            },
        }
    )

    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert len(events) == 2

    assert_action_trace(
        {
            "0": [{}],
            "0/repeat/sequence/0": [
                {
                    "result": {
                        "event": "test_event",
                        "event_data": {},
                    },
                    "variables": {
                        "repeat": {
                            "first": True,
                            "index": 1,
                            "last": False,
                            "item": "light.bulb_one",
                        }
                    },
                },
                {
                    "result": {
                        "event": "test_event",
                        "event_data": {},
                    },
                    "variables": {
                        "repeat": {
                            "first": False,
                            "index": 2,
                            "last": True,
                            "item": "light.bulb_two",
                        }
                    },
                },
            ],
        }
    )


async def test_repeat_for_each_non_list_template(hass: HomeAssistant) -> None:
    """Test repeat action using for each with a template not resulting in a list."""
    events = async_capture_events(hass, "test_event")
    sequence = cv.SCRIPT_SCHEMA(
        {
            "repeat": {
                "for_each": "{{ 'Not a list' }}",
                "sequence": {
                    "event": "test_event",
                },
            },
        }
    )

    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert len(events) == 0

    assert_action_trace(
        {
            "0": [
                {
                    "error_type": script._AbortScript,
                }
            ],
        },
        expected_script_execution="aborted",
    )


async def test_repeat_for_each_invalid_template(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test repeat action using for each with an invalid template."""
    events = async_capture_events(hass, "test_event")
    sequence = cv.SCRIPT_SCHEMA(
        {
            "repeat": {
                "for_each": "{{ Muhaha }}",
                "sequence": {
                    "event": "test_event",
                },
            },
        }
    )

    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert (
        "Test Name: Repeat 'for_each' must be a list of items in Test Name, got"
        in caplog.text
    )
    assert len(events) == 0

    assert_action_trace(
        {
            "0": [{"error_type": script._AbortScript}],
        },
        expected_script_execution="aborted",
    )


@pytest.mark.parametrize("condition", ["while", "until"])
async def test_repeat_condition_warning(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition
) -> None:
    """Test warning on repeat conditions."""
    event = "test_event"
    events = async_capture_events(hass, event)
    count = 0 if condition == "while" else 1

    sequence = {
        "repeat": {
            "sequence": [
                {
                    "event": event,
                },
            ],
        }
    }
    sequence["repeat"][condition] = {
        "condition": "numeric_state",
        "entity_id": "sensor.test",
        "value_template": "{{ unassigned_variable }}",
        "above": "0",
    }

    script_obj = script.Script(
        hass, cv.SCRIPT_SCHEMA(sequence), f"Test {condition}", "test_domain"
    )

    # wait_started = async_watch_for_action(script_obj, "wait")
    hass.states.async_set("sensor.test", "1")

    caplog.clear()
    caplog.set_level(logging.WARNING)

    hass.async_create_task(script_obj.async_run(context=Context()))
    await asyncio.wait_for(hass.async_block_till_done(), 1)

    assert f"Error in '{condition}[0]' evaluation" in caplog.text

    assert len(events) == count

    expected_trace = {"0": [{}]}
    if condition == "until":
        expected_trace["0/repeat/sequence/0"] = [
            {
                "result": {"event": "test_event", "event_data": {}},
                "variables": {"repeat": {"first": True, "index": 1}},
            }
        ]
    expected_trace["0/repeat"] = [
        {
            "result": {"result": None},
            "variables": {"repeat": {"first": True, "index": 1}},
        }
    ]
    expected_trace[f"0/repeat/{condition}/0"] = [{"error_type": ConditionError}]
    expected_trace[f"0/repeat/{condition}/0/entity_id/0"] = [
        {"error_type": ConditionError}
    ]
    assert_action_trace(expected_trace)


@pytest.mark.parametrize("condition", ["while", "until"])
@pytest.mark.parametrize("direct_template", [False, True])
async def test_repeat_conditional(
    hass: HomeAssistant, condition, direct_template
) -> None:
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
        template = "{{ not is_state('sensor.test', 'done') }}"
        if direct_template:
            sequence["repeat"]["while"] = template
        else:
            sequence["repeat"]["while"] = {
                "condition": "template",
                "value_template": template,
            }
    else:
        template = "{{ is_state('sensor.test', 'done') }}"
        if direct_template:
            sequence["repeat"]["until"] = template
        else:
            sequence["repeat"]["until"] = {
                "condition": "template",
                "value_template": template,
            }
    script_obj = script.Script(
        hass, cv.SCRIPT_SCHEMA(sequence), "Test Name", "test_domain"
    )

    wait_started = async_watch_for_action(script_obj, "wait")
    hass.states.async_set("sensor.test", "1")

    hass.async_create_task(script_obj.async_run(context=Context()))
    try:
        for index in range(2, count + 1):
            await asyncio.wait_for(wait_started.wait(), 1)
            wait_started.clear()
            hass.states.async_set("sensor.test", "next")
            await asyncio.wait_for(wait_started.wait(), 1)
            wait_started.clear()
            hass.states.async_set("sensor.test", index)
        await asyncio.wait_for(wait_started.wait(), 1)
        wait_started.clear()
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
        assert event.data.get("first") == (index == 0)
        assert event.data.get("index") == index + 1


async def test_repeat_until_condition_validation(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if we can use conditions in repeat until conditions which validate late."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        "test", "hue", "1234", suggested_object_id="entity"
    )
    assert entry.entity_id == "test.entity"
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {
                "repeat": {
                    "sequence": [
                        {"event": event},
                    ],
                    "until": [
                        {
                            "condition": "state",
                            "entity_id": entry.id,
                            "state": "hello",
                        }
                    ],
                }
            },
        ]
    )
    hass.states.async_set("test.entity", "hello")
    sequence = await script.async_validate_actions_config(hass, sequence)
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    caplog.clear()
    assert len(events) == 1

    assert_action_trace(
        {
            "0": [{"result": {}}],
            "0/repeat/sequence/0": [
                {
                    "result": {"event": "test_event", "event_data": {}},
                    "variables": {"repeat": {"first": True, "index": 1}},
                }
            ],
            "0/repeat": [
                {
                    "result": {"result": True},
                    "variables": {"repeat": {"first": True, "index": 1}},
                }
            ],
            "0/repeat/until/0": [{"result": {"result": True}}],
            "0/repeat/until/0/entity_id/0": [
                {"result": {"result": True, "state": "hello", "wanted_state": "hello"}}
            ],
        }
    )


async def test_repeat_while_condition_validation(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if we can use conditions in repeat while conditions which validate late."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        "test", "hue", "1234", suggested_object_id="entity"
    )
    assert entry.entity_id == "test.entity"
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {
                "repeat": {
                    "sequence": [
                        {"event": event},
                    ],
                    "while": [
                        {
                            "condition": "state",
                            "entity_id": entry.id,
                            "state": "hello",
                        }
                    ],
                }
            },
        ]
    )
    hass.states.async_set("test.entity", "goodbye")
    sequence = await script.async_validate_actions_config(hass, sequence)
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    caplog.clear()
    assert len(events) == 0

    assert_action_trace(
        {
            "0": [{"result": {}}],
            "0/repeat": [
                {
                    "result": {"result": False},
                    "variables": {"repeat": {"first": True, "index": 1}},
                }
            ],
            "0/repeat/while/0": [{"result": {"result": False}}],
            "0/repeat/while/0/entity_id/0": [
                {
                    "result": {
                        "result": False,
                        "state": "goodbye",
                        "wanted_state": "hello",
                    }
                }
            ],
        }
    )


@pytest.mark.parametrize("condition", ["while", "until"])
async def test_repeat_var_in_condition(hass: HomeAssistant, condition) -> None:
    """Test repeat action w/ while option."""
    event = "test_event"
    events = async_capture_events(hass, event)

    sequence = {"repeat": {"sequence": {"event": event}}}
    if condition == "while":
        value_template = "{{ repeat.index <= 2 }}"
    else:
        value_template = "{{ repeat.index == 2 }}"
    sequence["repeat"][condition] = {
        "condition": "template",
        "value_template": value_template,
    }

    script_obj = script.Script(
        hass, cv.SCRIPT_SCHEMA(sequence), "Test Name", "test_domain"
    )
    await script_obj.async_run(context=Context())
    assert len(events) == 2

    if condition == "while":
        expected_trace = {
            "0": [{}],
            "0/repeat": [
                {
                    "result": {"result": True},
                    "variables": {"repeat": {"first": True, "index": 1}},
                },
                {
                    "result": {"result": True},
                    "variables": {"repeat": {"first": False, "index": 2}},
                },
                {
                    "result": {"result": False},
                    "variables": {"repeat": {"first": False, "index": 3}},
                },
            ],
            "0/repeat/while/0": [
                {"result": {"entities": [], "result": True}},
                {"result": {"entities": [], "result": True}},
                {"result": {"entities": [], "result": False}},
            ],
            "0/repeat/sequence/0": [
                {"result": {"event": "test_event", "event_data": {}}}
            ]
            * 2,
        }
    else:
        expected_trace = {
            "0": [{}],
            "0/repeat/sequence/0": [
                {
                    "result": {"event": "test_event", "event_data": {}},
                    "variables": {"repeat": {"first": True, "index": 1}},
                },
                {
                    "result": {"event": "test_event", "event_data": {}},
                    "variables": {"repeat": {"first": False, "index": 2}},
                },
            ],
            "0/repeat": [
                {
                    "result": {"result": False},
                    "variables": {"repeat": {"first": True, "index": 1}},
                },
                {
                    "result": {"result": True},
                    "variables": {"repeat": {"first": False, "index": 2}},
                },
            ],
            "0/repeat/until/0": [
                {"result": {"entities": [], "result": False}},
                {"result": {"entities": [], "result": True}},
            ],
        }
    assert_action_trace(expected_trace)


@pytest.mark.parametrize(
    ("variables", "first_last", "inside_x"),
    [
        (None, {"repeat": None, "x": None}, None),
        (MappingProxyType({"x": 1}), {"repeat": None, "x": 1}, 1),
    ],
)
async def test_repeat_nested(
    hass: HomeAssistant, variables, first_last, inside_x
) -> None:
    """Test nested repeats."""
    event = "test_event"
    events = async_capture_events(hass, event)

    sequence = cv.SCRIPT_SCHEMA(
        [
            {
                "event": event,
                "event_data_template": {
                    "repeat": "{{ None if repeat is not defined else repeat }}",
                    "x": "{{ None if x is not defined else x }}",
                },
            },
            {
                "repeat": {
                    "count": 2,
                    "sequence": [
                        {
                            "event": event,
                            "event_data_template": {
                                "first": "{{ repeat.first }}",
                                "index": "{{ repeat.index }}",
                                "last": "{{ repeat.last }}",
                                "x": "{{ None if x is not defined else x }}",
                            },
                        },
                        {
                            "repeat": {
                                "count": 2,
                                "sequence": {
                                    "event": event,
                                    "event_data_template": {
                                        "first": "{{ repeat.first }}",
                                        "index": "{{ repeat.index }}",
                                        "last": "{{ repeat.last }}",
                                        "x": "{{ None if x is not defined else x }}",
                                    },
                                },
                            }
                        },
                        {
                            "event": event,
                            "event_data_template": {
                                "first": "{{ repeat.first }}",
                                "index": "{{ repeat.index }}",
                                "last": "{{ repeat.last }}",
                                "x": "{{ None if x is not defined else x }}",
                            },
                        },
                    ],
                }
            },
            {
                "event": event,
                "event_data_template": {
                    "repeat": "{{ None if repeat is not defined else repeat }}",
                    "x": "{{ None if x is not defined else x }}",
                },
            },
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    await script_obj.async_run(variables, Context())
    assert len(events) == 10
    assert events[0].data == first_last
    assert events[-1].data == first_last
    for index, result in enumerate(
        (
            (True, 1, False, inside_x),
            (True, 1, False, inside_x),
            (False, 2, True, inside_x),
            (True, 1, False, inside_x),
            (False, 2, True, inside_x),
            (True, 1, False, inside_x),
            (False, 2, True, inside_x),
            (False, 2, True, inside_x),
        ),
        1,
    ):
        assert events[index].data == {
            "first": result[0],
            "index": result[1],
            "last": result[2],
            "x": result[3],
        }

    event_data1 = {"repeat": None, "x": inside_x}
    event_data2 = [
        {"first": True, "index": 1, "last": False, "x": inside_x},
        {"first": False, "index": 2, "last": True, "x": inside_x},
    ]
    variable_repeat = [
        {"repeat": {"first": True, "index": 1, "last": False}},
        {"repeat": {"first": False, "index": 2, "last": True}},
    ]
    expected_trace = {
        "0": [{"result": {"event": "test_event", "event_data": event_data1}}],
        "1": [{}],
        "1/repeat/sequence/0": [
            {
                "result": {"event": "test_event", "event_data": event_data2[0]},
                "variables": variable_repeat[0],
            },
            {
                "result": {"event": "test_event", "event_data": event_data2[1]},
                "variables": variable_repeat[1],
            },
        ],
        "1/repeat/sequence/1": [{}, {}],
        "1/repeat/sequence/1/repeat/sequence/0": [
            {"result": {"event": "test_event", "event_data": event_data2[0]}},
            {
                "result": {"event": "test_event", "event_data": event_data2[1]},
                "variables": variable_repeat[1],
            },
            {
                "result": {"event": "test_event", "event_data": event_data2[0]},
                "variables": variable_repeat[0],
            },
            {"result": {"event": "test_event", "event_data": event_data2[1]}},
        ],
        "1/repeat/sequence/2": [
            {"result": {"event": "test_event", "event_data": event_data2[0]}},
            {"result": {"event": "test_event", "event_data": event_data2[1]}},
        ],
        "2": [{"result": {"event": "test_event", "event_data": event_data1}}],
    }
    assert_action_trace(expected_trace)


async def test_choose_warning(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test warning on choose."""
    event = "test_event"
    events = async_capture_events(hass, event)

    sequence = cv.SCRIPT_SCHEMA(
        {
            "choose": [
                {
                    "conditions": {
                        "condition": "numeric_state",
                        "entity_id": "test.entity",
                        "value_template": "{{ undefined_a + undefined_b }}",
                        "above": 1,
                    },
                    "sequence": {"event": event, "event_data": {"choice": "first"}},
                },
                {
                    "conditions": {
                        "condition": "numeric_state",
                        "entity_id": "test.entity",
                        "value_template": "{{ 'string' }}",
                        "above": 2,
                    },
                    "sequence": {"event": event, "event_data": {"choice": "second"}},
                },
            ],
            "default": {"event": event, "event_data": {"choice": "default"}},
        }
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    hass.states.async_set("test.entity", "9")
    await hass.async_block_till_done()

    caplog.clear()
    caplog.set_level(logging.WARNING)

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert len(caplog.record_tuples) == 2
    assert caplog.record_tuples[0][1] == logging.WARNING
    assert caplog.record_tuples[1][1] == logging.WARNING

    assert len(events) == 1
    assert events[0].data["choice"] == "default"


@pytest.mark.parametrize(
    ("var", "result"), [(1, "first"), (2, "second"), (3, "default")]
)
async def test_choose(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, var, result
) -> None:
    """Test choose action."""
    event = "test_event"
    events = async_capture_events(hass, event)
    alias = "choose step"
    choice = {1: "choice one", 2: "choice two", 3: None}
    aliases = {1: "sequence one", 2: "sequence two", 3: "default sequence"}
    sequence = cv.SCRIPT_SCHEMA(
        {
            "alias": alias,
            "choose": [
                {
                    "alias": choice[1],
                    "conditions": {
                        "condition": "template",
                        "value_template": "{{ var == 1 }}",
                    },
                    "sequence": {
                        "alias": aliases[1],
                        "event": event,
                        "event_data": {"choice": "first"},
                    },
                },
                {
                    "alias": choice[2],
                    "conditions": "{{ var == 2 }}",
                    "sequence": {
                        "alias": aliases[2],
                        "event": event,
                        "event_data": {"choice": "second"},
                    },
                },
            ],
            "default": {
                "alias": aliases[3],
                "event": event,
                "event_data": {"choice": "default"},
            },
        }
    )

    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(MappingProxyType({"var": var}), Context())
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["choice"] == result
    expected_choice = choice[var]
    if var == 3:
        expected_choice = "default"
    assert f"{alias}: {expected_choice}: Executing step {aliases[var]}" in caplog.text

    expected_choice = var - 1
    if var == 3:
        expected_choice = "default"

    expected_trace = {"0": [{"result": {"choice": expected_choice}}]}
    if var >= 1:
        expected_trace["0/choose/0"] = [{"result": {"result": var == 1}}]
        expected_trace["0/choose/0/conditions/0"] = [
            {"result": {"entities": [], "result": var == 1}}
        ]
    if var >= 2:
        expected_trace["0/choose/1"] = [{"result": {"result": var == 2}}]
        expected_trace["0/choose/1/conditions/0"] = [
            {"result": {"entities": [], "result": var == 2}}
        ]
    if var == 1:
        expected_trace["0/choose/0/sequence/0"] = [
            {"result": {"event": "test_event", "event_data": {"choice": "first"}}}
        ]
    if var == 2:
        expected_trace["0/choose/1/sequence/0"] = [
            {"result": {"event": "test_event", "event_data": {"choice": "second"}}}
        ]
    if var == 3:
        expected_trace["0/default/0"] = [
            {"result": {"event": "test_event", "event_data": {"choice": "default"}}}
        ]
    assert_action_trace(expected_trace)


async def test_choose_condition_validation(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if we can use conditions in choose actions which validate late."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        "test", "hue", "1234", suggested_object_id="entity"
    )
    assert entry.entity_id == "test.entity"
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {
                "choose": [
                    {
                        "alias": "choice one",
                        "conditions": {
                            "condition": "state",
                            "entity_id": entry.id,
                            "state": "hello",
                        },
                        "sequence": {
                            "alias": "sequence one",
                            "event": event,
                            "event_data": {"choice": "first"},
                        },
                    },
                ]
            },
        ]
    )
    sequence = await script.async_validate_actions_config(hass, sequence)
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    hass.states.async_set("test.entity", "hello")
    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    caplog.clear()
    assert len(events) == 2

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"result": {"choice": 0}}],
            "1/choose/0": [{"result": {"result": True}}],
            "1/choose/0/conditions/0": [{"result": {"result": True}}],
            "1/choose/0/conditions/0/entity_id/0": [
                {"result": {"result": True, "state": "hello", "wanted_state": "hello"}}
            ],
            "1/choose/0/sequence/0": [
                {"result": {"event": "test_event", "event_data": {"choice": "first"}}}
            ],
        }
    )

    hass.states.async_set("test.entity", "goodbye")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert len(events) == 3

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"result": {}}],
            "1/choose/0": [{"result": {"result": False}}],
            "1/choose/0/conditions/0": [{"result": {"result": False}}],
            "1/choose/0/conditions/0/entity_id/0": [
                {
                    "result": {
                        "result": False,
                        "state": "goodbye",
                        "wanted_state": "hello",
                    }
                }
            ],
        },
    )


@pytest.mark.parametrize(
    "action",
    [
        {"repeat": {"count": 1, "sequence": {"event": "abc"}}},
        {"choose": {"conditions": [], "sequence": {"event": "abc"}}},
        {"choose": [], "default": {"event": "abc"}},
    ],
)
async def test_multiple_runs_repeat_choose(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, action
) -> None:
    """Test parallel runs with repeat & choose actions & max_runs > default."""
    max_runs = script.DEFAULT_MAX + 1
    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(action),
        "Test Name",
        "test_domain",
        script_mode="parallel",
        max_runs=max_runs,
    )

    events = async_capture_events(hass, "abc")
    for _ in range(max_runs):
        hass.async_create_task(script_obj.async_run(context=Context()))
    await hass.async_block_till_done()

    assert "WARNING" not in caplog.text
    assert "ERROR" not in caplog.text
    assert len(events) == max_runs


async def test_if_warning(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test warning on if."""
    event = "test_event"
    events = async_capture_events(hass, event)

    sequence = cv.SCRIPT_SCHEMA(
        {
            "if": {
                "condition": "numeric_state",
                "entity_id": "test.entity",
                "value_template": "{{ undefined_a + undefined_b }}",
                "above": 1,
            },
            "then": {"event": event, "event_data": {"if": "then"}},
            "else": {"event": event, "event_data": {"if": "else"}},
        }
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    hass.states.async_set("test.entity", "9")
    await hass.async_block_till_done()

    caplog.clear()
    caplog.set_level(logging.WARNING)

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert len(caplog.record_tuples) == 1
    assert caplog.record_tuples[0][1] == logging.WARNING

    assert len(events) == 1
    assert events[0].data["if"] == "else"


@pytest.mark.parametrize(
    ("var", "if_result", "choice"), [(1, True, "then"), (2, False, "else")]
)
async def test_if(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    var: int,
    if_result: bool,
    choice: str,
) -> None:
    """Test if action."""
    events = async_capture_events(hass, "test_event")
    sequence = cv.SCRIPT_SCHEMA(
        {
            "if": {
                "alias": "if condition",
                "condition": "template",
                "value_template": "{{ var == 1 }}",
            },
            "then": {
                "alias": "if then",
                "event": "test_event",
                "event_data": {"if": "then"},
            },
            "else": {
                "alias": "if else",
                "event": "test_event",
                "event_data": {"if": "else"},
            },
        }
    )

    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(MappingProxyType({"var": var}), Context())
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["if"] == choice
    assert f"Test Name: If at step 1: Executing step if {choice}" in caplog.text

    expected_trace = {
        "0": [{"result": {"choice": choice}}],
        "0/if": [{"result": {"result": if_result}}],
        "0/if/condition/0": [{"result": {"result": var == 1, "entities": []}}],
        f"0/{choice}/0": [
            {"result": {"event": "test_event", "event_data": {"if": choice}}}
        ],
    }
    assert_action_trace(expected_trace)


async def test_if_disabled(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if action with a disabled condition."""
    sequence = cv.SCRIPT_SCHEMA(
        {
            "if": {
                "alias": "if condition",
                "condition": "template",
                "value_template": "{{ var == 1 }}",
                "enabled": "false",
            },
            "then": {
                "alias": "if then",
                "event": "test_event",
                "event_data": {"if": "then"},
            },
            "else": {
                "alias": "if else",
                "event": "test_event",
                "event_data": {"if": "else"},
            },
        }
    )

    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    expected_trace = {
        "0": [{"result": {"choice": "then"}}],
        "0/if": [{"result": {"result": True}}],
        "0/if/condition/0": [{"result": {"result": None}}],
        "0/then/0": [{"result": {"event": "test_event", "event_data": {"if": "then"}}}],
    }
    assert_action_trace(expected_trace)


async def test_if_condition_validation(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if we can use conditions in if actions which validate late."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        "test", "hue", "1234", suggested_object_id="entity"
    )
    assert entry.entity_id == "test.entity"
    events = async_capture_events(hass, "test_event")
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": "test_event"},
            {
                "if": {
                    "condition": "state",
                    "entity_id": entry.id,
                    "state": "hello",
                },
                "then": {
                    "event": "test_event",
                    "event_data": {"if": "then"},
                },
            },
        ]
    )
    sequence = await script.async_validate_actions_config(hass, sequence)
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    hass.states.async_set("test.entity", "hello")
    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    caplog.clear()
    assert len(events) == 2

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"result": {"choice": "then"}}],
            "1/if": [{"result": {"result": True}}],
            "1/if/condition/0": [{"result": {"result": True}}],
            "1/if/condition/0/entity_id/0": [
                {"result": {"result": True, "state": "hello", "wanted_state": "hello"}}
            ],
            "1/then/0": [
                {"result": {"event": "test_event", "event_data": {"if": "then"}}}
            ],
        }
    )

    hass.states.async_set("test.entity", "goodbye")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert len(events) == 3

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{}],
            "1/if": [{"result": {"result": False}}],
            "1/if/condition/0": [{"result": {"result": False}}],
            "1/if/condition/0/entity_id/0": [
                {
                    "result": {
                        "result": False,
                        "state": "goodbye",
                        "wanted_state": "hello",
                    }
                }
            ],
        },
    )


async def test_parallel(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test parallel action."""
    events = async_capture_events(hass, "test_event")
    hass.states.async_set("switch.trigger", "off")

    sequence = cv.SCRIPT_SCHEMA(
        {
            "parallel": [
                {
                    "alias": "Sequential group",
                    "sequence": [
                        {
                            "alias": "Waiting for trigger",
                            "wait_for_trigger": {
                                "platform": "state",
                                "entity_id": "switch.trigger",
                                "to": "on",
                            },
                        },
                        {
                            "event": "test_event",
                            "event_data": {
                                "hello": "from action 1",
                                "what": "{{ what }}",
                            },
                        },
                    ],
                },
                {
                    "alias": "Don't wait at all",
                    "event": "test_event",
                    "event_data": {"hello": "from action 2", "what": "{{ what }}"},
                },
            ]
        }
    )

    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    wait_started_flag = async_watch_for_action(script_obj, "Waiting for trigger")
    hass.async_create_task(
        script_obj.async_run(MappingProxyType({"what": "world"}), Context())
    )
    await asyncio.wait_for(wait_started_flag.wait(), 1)

    assert script_obj.is_running

    hass.states.async_set("switch.trigger", "on")
    await hass.async_block_till_done()

    assert len(events) == 2
    assert events[0].data["hello"] == "from action 2"
    assert events[0].data["what"] == "world"
    assert events[1].data["hello"] == "from action 1"
    assert events[1].data["what"] == "world"

    assert (
        "Test Name: Parallel action at step 1: Sequential group: Executing step Waiting"
        " for trigger" in caplog.text
    )
    assert (
        "Parallel action at step 1: parallel 2: Executing step Don't wait at all"
        in caplog.text
    )

    expected_trace = {
        "0": [{"result": {}}],
        "0/parallel/0/sequence/0": [
            {
                "result": {
                    "wait": {
                        "remaining": None,
                        "trigger": {
                            "entity_id": "switch.trigger",
                            "description": "state of switch.trigger",
                        },
                    }
                }
            }
        ],
        "0/parallel/1/sequence/0": [
            {
                "variables": {},
                "result": {
                    "event": "test_event",
                    "event_data": {"hello": "from action 2", "what": "world"},
                },
            }
        ],
        "0/parallel/0/sequence/1": [
            {
                "variables": {"wait": {"remaining": None}},
                "result": {
                    "event": "test_event",
                    "event_data": {"hello": "from action 1", "what": "world"},
                },
            }
        ],
    }
    assert_action_trace(expected_trace)


async def test_parallel_loop(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test parallel loops do not affect each other."""
    events_loop1 = async_capture_events(hass, "loop1")
    events_loop2 = async_capture_events(hass, "loop2")
    hass.states.async_set("switch.trigger", "off")

    sequence = cv.SCRIPT_SCHEMA(
        {
            "parallel": [
                {
                    "alias": "Loop1",
                    "sequence": [
                        {
                            "repeat": {
                                "for_each": ["loop1_a", "loop1_b", "loop1_c"],
                                "sequence": [
                                    {
                                        "event": "loop1",
                                        "event_data": {"hello1": "{{ repeat.item }}"},
                                    }
                                ],
                            },
                        },
                    ],
                },
                {
                    "alias": "Loop2",
                    "sequence": [
                        {
                            "repeat": {
                                "for_each": ["loop2_a", "loop2_b", "loop2_c"],
                                "sequence": [
                                    {
                                        "event": "loop2",
                                        "event_data": {"hello2": "{{ repeat.item }}"},
                                    }
                                ],
                            },
                        },
                    ],
                },
            ]
        }
    )

    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    hass.async_create_task(
        script_obj.async_run(MappingProxyType({"what": "world"}), Context())
    )
    await hass.async_block_till_done()

    assert len(events_loop1) == 3
    assert events_loop1[0].data["hello1"] == "loop1_a"
    assert events_loop1[1].data["hello1"] == "loop1_b"
    assert events_loop1[2].data["hello1"] == "loop1_c"
    assert events_loop2[0].data["hello2"] == "loop2_a"
    assert events_loop2[1].data["hello2"] == "loop2_b"
    assert events_loop2[2].data["hello2"] == "loop2_c"

    expected_trace = {
        "0": [{"result": {}}],
        "0/parallel/0/sequence/0": [{"result": {}}],
        "0/parallel/1/sequence/0": [
            {
                "result": {},
            }
        ],
        "0/parallel/0/sequence/0/repeat/sequence/0": [
            {
                "variables": {
                    "repeat": {
                        "first": True,
                        "index": 1,
                        "last": False,
                        "item": "loop1_a",
                    }
                },
                "result": {"event": "loop1", "event_data": {"hello1": "loop1_a"}},
            },
            {
                "variables": {
                    "repeat": {
                        "first": False,
                        "index": 2,
                        "last": False,
                        "item": "loop1_b",
                    }
                },
                "result": {"event": "loop1", "event_data": {"hello1": "loop1_b"}},
            },
            {
                "variables": {
                    "repeat": {
                        "first": False,
                        "index": 3,
                        "last": True,
                        "item": "loop1_c",
                    }
                },
                "result": {"event": "loop1", "event_data": {"hello1": "loop1_c"}},
            },
        ],
        "0/parallel/1/sequence/0/repeat/sequence/0": [
            {
                "variables": {
                    "repeat": {
                        "first": True,
                        "index": 1,
                        "last": False,
                        "item": "loop2_a",
                    }
                },
                "result": {"event": "loop2", "event_data": {"hello2": "loop2_a"}},
            },
            {
                "variables": {
                    "repeat": {
                        "first": False,
                        "index": 2,
                        "last": False,
                        "item": "loop2_b",
                    }
                },
                "result": {"event": "loop2", "event_data": {"hello2": "loop2_b"}},
            },
            {
                "variables": {
                    "repeat": {
                        "first": False,
                        "index": 3,
                        "last": True,
                        "item": "loop2_c",
                    }
                },
                "result": {"event": "loop2", "event_data": {"hello2": "loop2_c"}},
            },
        ],
    }
    assert_action_trace(expected_trace)


async def test_parallel_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test parallel action failure handling."""
    events = async_capture_events(hass, "test_event")
    sequence = cv.SCRIPT_SCHEMA(
        {
            "parallel": [
                {"service": "epic.failure"},
            ]
        }
    )

    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    with pytest.raises(exceptions.ServiceNotFound):
        await script_obj.async_run(context=Context())
    assert len(events) == 0

    expected_trace = {
        "0": [{"error_type": ServiceNotFound, "result": {}}],
        "0/parallel/0/sequence/0": [
            {
                "error_type": ServiceNotFound,
                "result": {
                    "params": {
                        "domain": "epic",
                        "service": "failure",
                        "service_data": {},
                        "target": {},
                    },
                    "running_script": False,
                },
            }
        ],
    }
    assert_action_trace(expected_trace, expected_script_execution="error")


async def test_last_triggered(hass: HomeAssistant) -> None:
    """Test the last_triggered."""
    event = "test_event"
    sequence = cv.SCRIPT_SCHEMA({"event": event})
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    assert script_obj.last_triggered is None

    time = dt_util.utcnow()
    with mock.patch("homeassistant.helpers.script.utcnow", return_value=time):
        await script_obj.async_run(context=Context())
        await hass.async_block_till_done()

    assert script_obj.last_triggered == time


async def test_propagate_error_service_not_found(hass: HomeAssistant) -> None:
    """Test that a script aborts when a service is not found."""
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA([{"service": "test.script"}, {"event": event}])
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    with pytest.raises(exceptions.ServiceNotFound):
        await script_obj.async_run(context=Context())

    assert len(events) == 0
    assert not script_obj.is_running

    expected_trace = {
        "0": [
            {
                "error_type": ServiceNotFound,
                "result": {
                    "params": {
                        "domain": "test",
                        "service": "script",
                        "service_data": {},
                        "target": {},
                    },
                    "running_script": False,
                },
            }
        ],
    }
    assert_action_trace(expected_trace, expected_script_execution="error")


async def test_propagate_error_invalid_service_data(hass: HomeAssistant) -> None:
    """Test that a script aborts when we send invalid service data."""
    event = "test_event"
    events = async_capture_events(hass, event)
    calls = async_mock_service(hass, "test", "script", vol.Schema({"text": str}))
    sequence = cv.SCRIPT_SCHEMA(
        [{"service": "test.script", "data": {"text": 1}}, {"event": event}]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    with pytest.raises(vol.Invalid):
        await script_obj.async_run(context=Context())

    assert len(events) == 0
    assert len(calls) == 0
    assert not script_obj.is_running

    expected_trace = {
        "0": [
            {
                "error_type": vol.MultipleInvalid,
                "result": {
                    "params": {
                        "domain": "test",
                        "service": "script",
                        "service_data": {"text": 1},
                        "target": {},
                    },
                    "running_script": False,
                },
            }
        ],
    }
    assert_action_trace(expected_trace, expected_script_execution="error")


async def test_propagate_error_service_exception(hass: HomeAssistant) -> None:
    """Test that a script aborts when a service throws an exception."""
    event = "test_event"
    events = async_capture_events(hass, event)

    @callback
    def record_call(service):
        """Add recorded event to set."""
        raise ValueError("BROKEN")

    hass.services.async_register("test", "script", record_call)

    sequence = cv.SCRIPT_SCHEMA([{"service": "test.script"}, {"event": event}])
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    with pytest.raises(ValueError):
        await script_obj.async_run(context=Context())

    assert len(events) == 0
    assert not script_obj.is_running

    expected_trace = {
        "0": [
            {
                "error_type": ValueError,
                "result": {
                    "params": {
                        "domain": "test",
                        "service": "script",
                        "service_data": {},
                        "target": {},
                    },
                    "running_script": False,
                },
            }
        ],
    }
    assert_action_trace(expected_trace, expected_script_execution="error")


async def test_referenced_areas(hass: HomeAssistant) -> None:
    """Test referenced areas."""
    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {
                    "service": "test.script",
                    "data": {"area_id": "area_service_not_list"},
                },
                {
                    "service": "test.script",
                    "data": {"area_id": ["area_service_list"]},
                },
                {
                    "service": "test.script",
                    "data": {"area_id": "{{ 'area_service_template' }}"},
                },
                {
                    "service": "test.script",
                    "target": {"area_id": "area_in_target"},
                },
                {
                    "service": "test.script",
                    "data_template": {"area_id": "area_in_data_template"},
                },
                {"service": "test.script", "data": {"without": "area_id"}},
                {
                    "choose": [
                        {
                            "conditions": "{{ true == false }}",
                            "sequence": [
                                {
                                    "service": "test.script",
                                    "data": {"area_id": "area_choice_1_seq"},
                                }
                            ],
                        },
                        {
                            "conditions": "{{ true == false }}",
                            "sequence": [
                                {
                                    "service": "test.script",
                                    "data": {"area_id": "area_choice_2_seq"},
                                }
                            ],
                        },
                    ],
                    "default": [
                        {
                            "service": "test.script",
                            "data": {"area_id": "area_default_seq"},
                        }
                    ],
                },
                {"event": "test_event"},
                {"delay": "{{ delay_period }}"},
                {
                    "if": [],
                    "then": [
                        {
                            "service": "test.script",
                            "data": {"area_id": "area_if_then"},
                        }
                    ],
                    "else": [
                        {
                            "service": "test.script",
                            "data": {"area_id": "area_if_else"},
                        }
                    ],
                },
                {
                    "parallel": [
                        {
                            "service": "test.script",
                            "data": {"area_id": "area_parallel"},
                        }
                    ],
                },
            ]
        ),
        "Test Name",
        "test_domain",
    )
    assert script_obj.referenced_areas == {
        "area_choice_1_seq",
        "area_choice_2_seq",
        "area_default_seq",
        "area_in_data_template",
        "area_in_target",
        "area_service_list",
        "area_service_not_list",
        "area_if_then",
        "area_if_else",
        "area_parallel",
        # 'area_service_template',  # no area extraction from template
    }
    # Test we cache results.
    assert script_obj.referenced_areas is script_obj.referenced_areas


async def test_referenced_entities(hass: HomeAssistant) -> None:
    """Test referenced entities."""
    script_obj = script.Script(
        hass,
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
                    "service": "test.script",
                    "data": {"entity_id": "{{ 'light.service_template' }}"},
                },
                {
                    "service": "test.script",
                    "entity_id": "light.direct_entity_referenced",
                },
                {
                    "service": "test.script",
                    "target": {"entity_id": "light.entity_in_target"},
                },
                {
                    "service": "test.script",
                    "data_template": {"entity_id": "light.entity_in_data_template"},
                },
                {
                    "condition": "state",
                    "entity_id": "sensor.condition",
                    "state": "100",
                },
                {"service": "test.script", "data": {"without": "entity_id"}},
                {"scene": "scene.hello"},
                {
                    "choose": [
                        {
                            "conditions": "{{ states.light.choice_1_cond == 'on' }}",
                            "sequence": [
                                {
                                    "service": "test.script",
                                    "data": {"entity_id": "light.choice_1_seq"},
                                }
                            ],
                        },
                        {
                            "conditions": {
                                "condition": "state",
                                "entity_id": "light.choice_2_cond",
                                "state": "on",
                            },
                            "sequence": [
                                {
                                    "service": "test.script",
                                    "data": {"entity_id": "light.choice_2_seq"},
                                }
                            ],
                        },
                    ],
                    "default": [
                        {
                            "service": "test.script",
                            "data": {"entity_id": "light.default_seq"},
                        }
                    ],
                },
                {"event": "test_event"},
                {"delay": "{{ delay_period }}"},
                {
                    "if": [],
                    "then": [
                        {
                            "service": "test.script",
                            "data": {"entity_id": "light.if_then"},
                        }
                    ],
                    "else": [
                        {
                            "service": "test.script",
                            "data": {"entity_id": "light.if_else"},
                        }
                    ],
                },
                {
                    "parallel": [
                        {
                            "service": "test.script",
                            "data": {"entity_id": "light.parallel"},
                        }
                    ],
                },
            ]
        ),
        "Test Name",
        "test_domain",
    )
    assert script_obj.referenced_entities == {
        # "light.choice_1_cond",  # no entity extraction from template conditions
        "light.choice_1_seq",
        "light.choice_2_cond",
        "light.choice_2_seq",
        "light.default_seq",
        "light.direct_entity_referenced",
        "light.entity_in_data_template",
        "light.entity_in_target",
        "light.service_list",
        "light.service_not_list",
        "light.if_then",
        "light.if_else",
        "light.parallel",
        # "light.service_template",  # no entity extraction from template
        "scene.hello",
        "sensor.condition",
    }
    # Test we cache results.
    assert script_obj.referenced_entities is script_obj.referenced_entities


async def test_referenced_devices(hass: HomeAssistant) -> None:
    """Test referenced entities."""
    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"domain": "light", "device_id": "script-dev-id"},
                {
                    "condition": "device",
                    "device_id": "condition-dev-id",
                    "domain": "switch",
                },
                {
                    "service": "test.script",
                    "data": {"device_id": "data-string-id"},
                },
                {
                    "service": "test.script",
                    "data_template": {"device_id": "data-template-string-id"},
                },
                {
                    "service": "test.script",
                    "target": {"device_id": "target-string-id"},
                },
                {
                    "service": "test.script",
                    "target": {"device_id": ["target-list-id-1", "target-list-id-2"]},
                },
                {
                    "choose": [
                        {
                            "conditions": (
                                "{{ is_device_attr('choice-2-cond-dev-id', 'model',"
                                " 'blah') }}"
                            ),
                            "sequence": [
                                {
                                    "service": "test.script",
                                    "target": {
                                        "device_id": "choice-1-seq-device-target"
                                    },
                                }
                            ],
                        },
                        {
                            "conditions": {
                                "condition": "device",
                                "device_id": "choice-2-cond-dev-id",
                                "domain": "switch",
                            },
                            "sequence": [
                                {
                                    "service": "test.script",
                                    "target": {
                                        "device_id": "choice-2-seq-device-target"
                                    },
                                }
                            ],
                        },
                    ],
                    "default": [
                        {
                            "service": "test.script",
                            "target": {"device_id": "default-device-target"},
                        }
                    ],
                },
                {
                    "if": [],
                    "then": [
                        {
                            "service": "test.script",
                            "data": {"device_id": "if-then"},
                        }
                    ],
                    "else": [
                        {
                            "service": "test.script",
                            "data": {"device_id": "if-else"},
                        }
                    ],
                },
                {
                    "parallel": [
                        {
                            "service": "test.script",
                            "target": {"device_id": "parallel-device"},
                        }
                    ],
                },
            ]
        ),
        "Test Name",
        "test_domain",
    )
    assert script_obj.referenced_devices == {
        # 'choice-1-cond-dev-id',  # no device extraction from template conditions
        "choice-1-seq-device-target",
        "choice-2-cond-dev-id",
        "choice-2-seq-device-target",
        "condition-dev-id",
        "data-string-id",
        "data-template-string-id",
        "default-device-target",
        "script-dev-id",
        "target-list-id-1",
        "target-list-id-2",
        "target-string-id",
        "if-then",
        "if-else",
        "parallel-device",
    }
    # Test we cache results.
    assert script_obj.referenced_devices is script_obj.referenced_devices


@contextmanager
def does_not_raise():
    """Indicate no exception is expected."""
    yield


async def test_script_mode_single(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
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
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run(context=Context()))
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 1
        assert events[0].data["value"] == 1

        # Start second run of script while first run is suspended in wait_template.

        await script_obj.async_run(context=Context())

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


@pytest.mark.parametrize("max_exceeded", [None, "WARNING", "INFO", "ERROR", "SILENT"])
@pytest.mark.parametrize(
    ("script_mode", "max_runs"), [("single", 1), ("parallel", 2), ("queued", 2)]
)
async def test_max_exceeded(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    max_exceeded,
    script_mode,
    max_runs,
) -> None:
    """Test max_exceeded option."""
    sequence = cv.SCRIPT_SCHEMA(
        {"wait_template": "{{ states.switch.test.state == 'off' }}"}
    )
    if max_exceeded is None:
        script_obj = script.Script(
            hass,
            sequence,
            "Test Name",
            "test_domain",
            script_mode=script_mode,
            max_runs=max_runs,
        )
    else:
        script_obj = script.Script(
            hass,
            sequence,
            "Test Name",
            "test_domain",
            script_mode=script_mode,
            max_runs=max_runs,
            max_exceeded=max_exceeded,
        )
    hass.states.async_set("switch.test", "on")
    for _ in range(max_runs + 1):
        hass.async_create_task(script_obj.async_run(context=Context()))
    hass.states.async_set("switch.test", "off")
    await hass.async_block_till_done()
    if max_exceeded is None:
        max_exceeded = "WARNING"
    if max_exceeded == "SILENT":
        assert not any(
            any(
                message in rec.message
                for message in ("Already running", "Maximum number of runs exceeded")
            )
            for rec in caplog.records
        )
    else:
        assert any(
            rec.levelname == max_exceeded
            and any(
                message in rec.message
                for message in ("Already running", "Maximum number of runs exceeded")
            )
            for rec in caplog.records
        )


@pytest.mark.parametrize(
    ("script_mode", "messages", "last_events"),
    [("restart", ["Restarting"], [2]), ("parallel", [], [2, 2])],
)
async def test_script_mode_2(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    script_mode,
    messages,
    last_events,
) -> None:
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
        hass,
        sequence,
        "Test Name",
        "test_domain",
        script_mode=script_mode,
        max_runs=max_runs,
        logger=logger,
    )
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    try:
        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run(context=Context()))
        await asyncio.wait_for(wait_started_flag.wait(), 1)

        assert script_obj.is_running
        assert len(events) == 1
        assert events[0].data["value"] == 1

        # Start second run of script while first run is suspended in wait_template.

        wait_started_flag.clear()
        hass.async_create_task(script_obj.async_run(context=Context()))
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


async def test_script_mode_queued(hass: HomeAssistant) -> None:
    """Test overlapping runs with script_mode = 'queued' & max_runs > 1."""
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event, "event_data": {"value": 1}},
            {
                "wait_template": "{{ states.switch.test.state == 'off' }}",
                "alias": "wait_1",
            },
            {"event": event, "event_data": {"value": 2}},
            {
                "wait_template": "{{ states.switch.test.state == 'on' }}",
                "alias": "wait_2",
            },
        ]
    )
    logger = logging.getLogger("TEST")
    script_obj = script.Script(
        hass,
        sequence,
        "Test Name",
        "test_domain",
        script_mode="queued",
        max_runs=2,
        logger=logger,
    )

    watch_messages = []

    @callback
    def check_action():
        for message, flag in watch_messages:
            if script_obj.last_action and message in script_obj.last_action:
                flag.set()

    script_obj.change_listener = check_action
    wait_started_flag_1 = asyncio.Event()
    watch_messages.append(("wait_1", wait_started_flag_1))
    wait_started_flag_2 = asyncio.Event()
    watch_messages.append(("wait_2", wait_started_flag_2))

    try:
        assert not script_obj.is_running
        assert script_obj.runs == 0

        hass.states.async_set("switch.test", "on")
        hass.async_create_task(script_obj.async_run(context=Context()))
        await asyncio.wait_for(wait_started_flag_1.wait(), 1)

        assert script_obj.is_running
        assert script_obj.runs == 1
        assert len(events) == 1
        assert events[0].data["value"] == 1

        # Start second run of script while first run is suspended in wait_template.
        # This second run should not start until the first run has finished.

        hass.async_create_task(script_obj.async_run(context=Context()))
        await asyncio.sleep(0)

        assert script_obj.is_running
        assert script_obj.runs == 2
        assert len(events) == 1

        hass.states.async_set("switch.test", "off")
        await asyncio.wait_for(wait_started_flag_2.wait(), 1)

        assert script_obj.is_running
        assert script_obj.runs == 2
        assert len(events) == 2
        assert events[1].data["value"] == 2

        wait_started_flag_1.clear()
        hass.states.async_set("switch.test", "on")
        await asyncio.wait_for(wait_started_flag_1.wait(), 1)

        assert script_obj.is_running
        assert script_obj.runs == 1
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
        assert script_obj.runs == 0
        assert len(events) == 4
        assert events[3].data["value"] == 2


async def test_script_mode_queued_cancel(hass: HomeAssistant) -> None:
    """Test canceling with a queued run."""
    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA({"wait_template": "{{ false }}"}),
        "Test Name",
        "test_domain",
        script_mode="queued",
        max_runs=2,
    )
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    try:
        assert not script_obj.is_running
        assert script_obj.runs == 0

        task1 = hass.async_create_task(script_obj.async_run(context=Context()))
        await asyncio.wait_for(wait_started_flag.wait(), 1)
        task2 = hass.async_create_task(script_obj.async_run(context=Context()))
        await asyncio.sleep(0)

        assert script_obj.is_running
        assert script_obj.runs == 2

        with pytest.raises(asyncio.CancelledError):
            task2.cancel()
            await task2

        assert script_obj.is_running
        assert script_obj.runs == 1

        with pytest.raises(asyncio.CancelledError):
            task1.cancel()
            await task1

        assert not script_obj.is_running
        assert script_obj.runs == 0
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise


async def test_script_mode_queued_stop(hass: HomeAssistant) -> None:
    """Test stopping with a queued run."""
    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA({"wait_template": "{{ false }}"}),
        "Test Name",
        "test_domain",
        script_mode="queued",
        max_runs=3,
    )
    wait_started_flag = async_watch_for_action(script_obj, "wait")

    assert not script_obj.is_running
    assert script_obj.runs == 0

    hass.async_create_task(script_obj.async_run(context=Context()))
    await asyncio.wait_for(wait_started_flag.wait(), 1)
    hass.async_create_task(script_obj.async_run(context=Context()))
    await asyncio.sleep(0)
    hass.async_create_task(script_obj.async_run(context=Context()))
    await asyncio.sleep(0)

    assert script_obj.is_running
    assert script_obj.runs == 3

    await script_obj.async_stop()

    assert not script_obj.is_running
    assert script_obj.runs == 0


async def test_script_logging(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test script logging."""
    script_obj = script.Script(hass, [], "Script with % Name", "test_domain")
    script_obj._log("Test message with name %s", 1)

    assert "Script with % Name: Test message with name 1" in caplog.text


async def test_shutdown_at(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test stopping scripts at shutdown."""
    delay_alias = "delay step"
    sequence = cv.SCRIPT_SCHEMA({"delay": {"seconds": 120}, "alias": delay_alias})
    script_obj = script.Script(hass, sequence, "test script", "test_domain")
    delay_started_flag = async_watch_for_action(script_obj, delay_alias)

    try:
        hass.async_create_task(script_obj.async_run(context=Context()))
        await asyncio.wait_for(delay_started_flag.wait(), 1)

        assert script_obj.is_running
        assert script_obj.last_action == delay_alias
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        hass.bus.async_fire("homeassistant_stop")
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert "Stopping scripts running at shutdown: test script" in caplog.text

    expected_trace = {
        "0": [{"result": {"delay": 120.0, "done": False}}],
    }
    assert_action_trace(expected_trace)


@pytest.mark.parametrize("wait_for_stop_scripts_after_shutdown", [True])
async def test_shutdown_after(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test stopping scripts at shutdown."""
    delay_alias = "delay step"
    sequence = cv.SCRIPT_SCHEMA({"delay": {"seconds": 120}, "alias": delay_alias})
    script_obj = script.Script(hass, sequence, "test script", "test_domain")
    delay_started_flag = async_watch_for_action(script_obj, delay_alias)

    hass.state = CoreState.stopping
    hass.bus.async_fire("homeassistant_stop")
    await hass.async_block_till_done()

    try:
        hass.async_create_task(script_obj.async_run(context=Context()))
        await asyncio.wait_for(delay_started_flag.wait(), 1)

        assert script_obj.is_running
        assert script_obj.last_action == delay_alias
    except (AssertionError, asyncio.TimeoutError):
        await script_obj.async_stop()
        raise
    else:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
        await hass.async_block_till_done()

        assert not script_obj.is_running
        assert (
            "Stopping scripts running too long after shutdown: test script"
            in caplog.text
        )

    expected_trace = {
        "0": [{"result": {"delay": 120.0, "done": False}}],
    }
    assert_action_trace(expected_trace)


@pytest.mark.parametrize("wait_for_stop_scripts_after_shutdown", [True])
async def test_start_script_after_shutdown(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test starting scripts after shutdown is blocked."""
    delay_alias = "delay step"
    sequence = cv.SCRIPT_SCHEMA({"delay": {"seconds": 120}, "alias": delay_alias})
    script_obj = script.Script(hass, sequence, "test script", "test_domain")

    # Trigger 1st stage script shutdown
    hass.state = CoreState.stopping
    hass.bus.async_fire("homeassistant_stop")
    await hass.async_block_till_done()
    # Trigger 2nd stage script shutdown
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()

    # Attempt to spawn additional script run
    await script_obj.async_run(context=Context())
    assert not script_obj.is_running
    assert "Home Assistant is shutting down, starting script blocked" in caplog.text


async def test_update_logger(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test updating logger."""
    sequence = cv.SCRIPT_SCHEMA({"event": "test_event"})
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert script.__name__ in caplog.text

    log_name = "testing.123"
    script_obj.update_logger(logging.getLogger(log_name))

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert log_name in caplog.text


async def test_started_action(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the callback of started_action."""
    event = "test_event"
    log_message = "The script started!"
    logger = logging.getLogger("TEST")

    sequence = cv.SCRIPT_SCHEMA({"event": event})
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    @callback
    def started_action():
        logger.info(log_message)

    await script_obj.async_run(context=Context(), started_action=started_action)
    await hass.async_block_till_done()

    assert log_message in caplog.text


async def test_set_variable(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setting variables in scripts."""
    alias = "variables step"
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"alias": alias, "variables": {"variable": "value"}},
            {"service": "test.script", "data": {"value": "{{ variable }}"}},
        ]
    )
    script_obj = script.Script(hass, sequence, "test script", "test_domain")

    mock_calls = async_mock_service(hass, "test", "script")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert mock_calls[0].data["value"] == "value"
    assert f"Executing step {alias}" in caplog.text

    expected_trace = {
        "0": [{}],
        "1": [
            {
                "result": {
                    "params": {
                        "domain": "test",
                        "service": "script",
                        "service_data": {"value": "value"},
                        "target": {},
                    },
                    "running_script": False,
                },
                "variables": {"variable": "value"},
            }
        ],
    }
    assert_action_trace(expected_trace)


async def test_set_redefines_variable(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setting variables based on their current value."""
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"variables": {"variable": "1"}},
            {"service": "test.script", "data": {"value": "{{ variable }}"}},
            {"variables": {"variable": "{{ variable | int + 1 }}"}},
            {"service": "test.script", "data": {"value": "{{ variable }}"}},
        ]
    )
    script_obj = script.Script(hass, sequence, "test script", "test_domain")

    mock_calls = async_mock_service(hass, "test", "script")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert mock_calls[0].data["value"] == 1
    assert mock_calls[1].data["value"] == 2

    expected_trace = {
        "0": [{}],
        "1": [
            {
                "result": {
                    "params": {
                        "domain": "test",
                        "service": "script",
                        "service_data": {"value": 1},
                        "target": {},
                    },
                    "running_script": False,
                },
                "variables": {"variable": "1"},
            }
        ],
        "2": [{}],
        "3": [
            {
                "result": {
                    "params": {
                        "domain": "test",
                        "service": "script",
                        "service_data": {"value": 2},
                        "target": {},
                    },
                    "running_script": False,
                },
                "variables": {"variable": 2},
            }
        ],
    }
    assert_action_trace(expected_trace)


async def test_validate_action_config(hass: HomeAssistant) -> None:
    """Validate action config."""

    def templated_device_action(message):
        return {
            "device_id": "abcd",
            "domain": "mobile_app",
            "message": f"{message} {{{{ 5 + 5}}}}",
            "type": "notify",
        }

    configs = {
        cv.SCRIPT_ACTION_CALL_SERVICE: {"service": "light.turn_on"},
        cv.SCRIPT_ACTION_DELAY: {"delay": 5},
        cv.SCRIPT_ACTION_WAIT_TEMPLATE: {
            "wait_template": "{{ states.light.kitchen.state == 'on' }}"
        },
        cv.SCRIPT_ACTION_FIRE_EVENT: {"event": "my_event"},
        cv.SCRIPT_ACTION_CHECK_CONDITION: {
            "condition": "state",
            "entity_id": "light.kitchen",
            "state": "on",
        },
        cv.SCRIPT_ACTION_DEVICE_AUTOMATION: templated_device_action("device"),
        cv.SCRIPT_ACTION_ACTIVATE_SCENE: {"scene": "scene.relax"},
        cv.SCRIPT_ACTION_REPEAT: {
            "repeat": {
                "count": 3,
                "sequence": [templated_device_action("repeat_event")],
            }
        },
        cv.SCRIPT_ACTION_CHOOSE: {
            "choose": [
                {
                    "conditions": "{{ states.light.kitchen.state == 'on' }}",
                    "sequence": [templated_device_action("choose_event")],
                }
            ],
            "default": [templated_device_action("choose_default_event")],
        },
        cv.SCRIPT_ACTION_WAIT_FOR_TRIGGER: {
            "wait_for_trigger": [
                {"platform": "event", "event_type": "wait_for_trigger_event"}
            ]
        },
        cv.SCRIPT_ACTION_VARIABLES: {"variables": {"hello": "world"}},
        cv.SCRIPT_ACTION_STOP: {"stop": "Stop it right there buddy..."},
        cv.SCRIPT_ACTION_IF: {
            "if": [
                {
                    "condition": "state",
                    "entity_id": "light.kitchen",
                    "state": "on",
                },
            ],
            "then": [templated_device_action("if_then_event")],
            "else": [templated_device_action("if_else_event")],
        },
        cv.SCRIPT_ACTION_PARALLEL: {
            "parallel": [templated_device_action("parallel_event")],
        },
    }
    expected_templates = {
        cv.SCRIPT_ACTION_CHECK_CONDITION: None,
        cv.SCRIPT_ACTION_DEVICE_AUTOMATION: [[]],
        cv.SCRIPT_ACTION_REPEAT: [["repeat", "sequence", 0]],
        cv.SCRIPT_ACTION_CHOOSE: [["choose", 0, "sequence", 0], ["default", 0]],
        cv.SCRIPT_ACTION_WAIT_FOR_TRIGGER: None,
        cv.SCRIPT_ACTION_IF: None,
        cv.SCRIPT_ACTION_PARALLEL: None,
    }

    for key in cv.ACTION_TYPE_SCHEMAS:
        assert key in configs, f"No validate config test found for {key}"
        assert key in expected_templates or key in script.STATIC_VALIDATION_ACTION_TYPES

    # Verify we raise if we don't know the action type
    with patch(
        "homeassistant.helpers.config_validation.determine_script_action",
        return_value="non-existing",
    ), pytest.raises(ValueError):
        await script.async_validate_action_config(hass, {})

    # Verify each action can validate
    validated_config = {}
    for action_type, config in configs.items():
        assert cv.determine_script_action(config) == action_type
        try:
            validated_config[action_type] = cv.ACTION_TYPE_SCHEMAS[action_type](config)
            validated_config[action_type] = await script.async_validate_action_config(
                hass, validated_config[action_type]
            )
        except vol.Invalid as err:
            pytest.fail(f"{action_type} config invalid: {err}")

    # Verify non-static actions have validated
    for action_type, paths_to_templates in expected_templates.items():
        if paths_to_templates is None:
            continue
        for path_to_template in paths_to_templates:
            device_action = reduce(
                operator.getitem, path_to_template, validated_config[action_type]
            )
            assert isinstance(device_action["message"], template.Template)


async def test_embedded_wait_for_trigger_in_automation(hass: HomeAssistant) -> None:
    """Test an embedded wait for trigger."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {
                    "repeat": {
                        "while": [
                            {
                                "condition": "template",
                                "value_template": (
                                    '{{ is_state("test.value1", "trigger-while") }}'
                                ),
                            }
                        ],
                        "sequence": [
                            {"event": "trigger_wait_event"},
                            {
                                "wait_for_trigger": [
                                    {
                                        "platform": "template",
                                        "value_template": (
                                            '{{ is_state("test.value2",'
                                            ' "trigger-wait") }}'
                                        ),
                                    }
                                ]
                            },
                            {"service": "test.script"},
                        ],
                    }
                },
            }
        },
    )

    hass.states.async_set("test.value1", "trigger-while")
    hass.states.async_set("test.value2", "not-trigger-wait")
    mock_calls = async_mock_service(hass, "test", "script")

    async def trigger_wait_event(_):
        # give script the time to attach the trigger.
        await asyncio.sleep(0)
        hass.states.async_set("test.value1", "not-trigger-while")
        hass.states.async_set("test.value2", "trigger-wait")

    hass.bus.async_listen("trigger_wait_event", trigger_wait_event)

    # Start automation
    hass.bus.async_fire("test_event")

    await hass.async_block_till_done()

    assert len(mock_calls) == 1


async def test_breakpoints_1(hass: HomeAssistant) -> None:
    """Test setting a breakpoint halts execution, and execution can be resumed."""
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event, "event_data": {"value": 0}},  # Node "0"
            {"event": event, "event_data": {"value": 1}},  # Node "1"
            {"event": event, "event_data": {"value": 2}},  # Node "2"
            {"event": event, "event_data": {"value": 3}},  # Node "3"
            {"event": event, "event_data": {"value": 4}},  # Node "4"
            {"event": event, "event_data": {"value": 5}},  # Node "5"
            {"event": event, "event_data": {"value": 6}},  # Node "6"
            {"event": event, "event_data": {"value": 7}},  # Node "7"
        ]
    )
    logger = logging.getLogger("TEST")
    script_obj = script.Script(
        hass,
        sequence,
        "Test Name",
        "test_domain",
        script_mode="queued",
        max_runs=2,
        logger=logger,
    )
    trace.trace_id_set(("script_1", "1"))
    script.breakpoint_set(hass, "script_1", script.RUN_ID_ANY, "1")
    script.breakpoint_set(hass, "script_1", script.RUN_ID_ANY, "5")

    breakpoint_hit_event = asyncio.Event()

    @callback
    def breakpoint_hit(*_):
        breakpoint_hit_event.set()

    async_dispatcher_connect(hass, script.SCRIPT_BREAKPOINT_HIT, breakpoint_hit)

    watch_messages = []

    @callback
    def check_action():
        for message, flag in watch_messages:
            if script_obj.last_action and message in script_obj.last_action:
                flag.set()

    script_obj.change_listener = check_action

    assert not script_obj.is_running
    assert script_obj.runs == 0

    # Start script, should stop on breakpoint at node "1"
    hass.async_create_task(script_obj.async_run(context=Context()))
    await breakpoint_hit_event.wait()
    assert script_obj.is_running
    assert script_obj.runs == 1
    assert len(events) == 1
    assert events[-1].data["value"] == 0

    # Single step script, should stop at node "2"
    breakpoint_hit_event.clear()
    script.debug_step(hass, "script_1", "1")
    await breakpoint_hit_event.wait()
    assert script_obj.is_running
    assert script_obj.runs == 1
    assert len(events) == 2
    assert events[-1].data["value"] == 1

    # Single step script, should stop at node "3"
    breakpoint_hit_event.clear()
    script.debug_step(hass, "script_1", "1")
    await breakpoint_hit_event.wait()
    assert script_obj.is_running
    assert script_obj.runs == 1
    assert len(events) == 3
    assert events[-1].data["value"] == 2

    # Resume script, should stop on breakpoint at node "5"
    breakpoint_hit_event.clear()
    script.debug_continue(hass, "script_1", "1")
    await breakpoint_hit_event.wait()
    assert script_obj.is_running
    assert script_obj.runs == 1
    assert len(events) == 5
    assert events[-1].data["value"] == 4

    # Resume script, should run until completion
    script.debug_continue(hass, "script_1", "1")
    await hass.async_block_till_done()
    assert not script_obj.is_running
    assert script_obj.runs == 0
    assert len(events) == 8
    assert events[-1].data["value"] == 7


async def test_breakpoints_2(hass: HomeAssistant) -> None:
    """Test setting a breakpoint halts execution, and execution can be aborted."""
    event = "test_event"
    events = async_capture_events(hass, event)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event, "event_data": {"value": 0}},  # Node "0"
            {"event": event, "event_data": {"value": 1}},  # Node "1"
            {"event": event, "event_data": {"value": 2}},  # Node "2"
            {"event": event, "event_data": {"value": 3}},  # Node "3"
            {"event": event, "event_data": {"value": 4}},  # Node "4"
            {"event": event, "event_data": {"value": 5}},  # Node "5"
            {"event": event, "event_data": {"value": 6}},  # Node "6"
            {"event": event, "event_data": {"value": 7}},  # Node "7"
        ]
    )
    logger = logging.getLogger("TEST")
    script_obj = script.Script(
        hass,
        sequence,
        "Test Name",
        "test_domain",
        script_mode="queued",
        max_runs=2,
        logger=logger,
    )
    trace.trace_id_set(("script_1", "1"))
    script.breakpoint_set(hass, "script_1", script.RUN_ID_ANY, "1")
    script.breakpoint_set(hass, "script_1", script.RUN_ID_ANY, "5")

    breakpoint_hit_event = asyncio.Event()

    @callback
    def breakpoint_hit(*_):
        breakpoint_hit_event.set()

    async_dispatcher_connect(hass, script.SCRIPT_BREAKPOINT_HIT, breakpoint_hit)

    watch_messages = []

    @callback
    def check_action():
        for message, flag in watch_messages:
            if script_obj.last_action and message in script_obj.last_action:
                flag.set()

    script_obj.change_listener = check_action

    assert not script_obj.is_running
    assert script_obj.runs == 0

    # Start script, should stop on breakpoint at node "1"
    hass.async_create_task(script_obj.async_run(context=Context()))
    await breakpoint_hit_event.wait()
    assert script_obj.is_running
    assert script_obj.runs == 1
    assert len(events) == 1
    assert events[-1].data["value"] == 0

    # Abort script
    script.debug_stop(hass, "script_1", "1")
    await hass.async_block_till_done()
    assert not script_obj.is_running
    assert script_obj.runs == 0
    assert len(events) == 1


async def test_platform_async_validate_action_config(hass: HomeAssistant) -> None:
    """Test platform.async_validate_action_config will be called if it exists."""
    config = {CONF_DEVICE_ID: "test", CONF_DOMAIN: "test"}
    with patch(
        "homeassistant.components.device_automation.action.async_validate_action_config",
        return_value=AsyncMock(),
    ) as device_automation_validate_action_mock:
        await script.async_validate_action_config(hass, config)
        device_automation_validate_action_mock.assert_awaited()


async def test_stop_action(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if automation stops on calling the stop action."""
    event = "test_event"
    events = async_capture_events(hass, event)

    alias = "stop step"
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {
                "alias": alias,
                "stop": "In the name of love",
            },
            {"event": event},
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert "Stop script sequence: In the name of love" in caplog.text
    caplog.clear()
    assert len(events) == 1

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"result": {"stop": "In the name of love", "error": False}}],
        }
    )


@pytest.mark.parametrize(
    ("error", "error_type", "logmsg", "script_execution"),
    (
        (True, script._AbortScript, "Error", "aborted"),
        (False, None, "Stop", "finished"),
    ),
)
async def test_stop_action_subscript(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    error,
    error_type,
    logmsg,
    script_execution,
) -> None:
    """Test if automation stops on calling the stop action from a sub-script."""
    event = "test_event"
    events = async_capture_events(hass, event)

    alias = "stop step"
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {
                "if": {
                    "alias": "if condition",
                    "condition": "template",
                    "value_template": "{{ 1 == 1 }}",
                },
                "then": {
                    "alias": alias,
                    "stop": "In the name of love",
                    "error": error,
                },
            },
            {"event": event},
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert f"{logmsg} script sequence: In the name of love" in caplog.text
    caplog.clear()
    assert len(events) == 1

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"error_type": error_type, "result": {"choice": "then"}}],
            "1/if": [{"result": {"result": True}}],
            "1/if/condition/0": [{"result": {"result": True, "entities": []}}],
            "1/then/0": [
                {
                    "error_type": error_type,
                    "result": {"stop": "In the name of love", "error": error},
                }
            ],
        },
        expected_script_execution=script_execution,
    )


async def test_stop_action_with_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if automation fails on calling the error action."""
    event = "test_event"
    events = async_capture_events(hass, event)

    alias = "stop step"
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": event},
            {
                "alias": alias,
                "stop": "Epic one...",
                "error": True,
            },
            {"event": event},
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert "Test Name: Error script sequence: Epic one..." in caplog.text
    caplog.clear()
    assert len(events) == 1

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [
                {
                    "error_type": script._AbortScript,
                    "result": {"stop": "Epic one...", "error": True},
                }
            ],
        },
        expected_script_execution="aborted",
    )


async def test_continue_on_error(hass: HomeAssistant) -> None:
    """Test if automation continue when a step fails."""
    events = async_capture_events(hass, "test_event")

    @callback
    def broken_service(service: ServiceCall) -> None:
        """Break this service with an error."""
        raise HomeAssistantError("It is not working!")

    hass.services.async_register("broken", "service", broken_service)

    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": "test_event"},
            {
                "continue_on_error": True,
                "service": "broken.service",
            },
            {"event": "test_event"},
            {
                "continue_on_error": False,
                "service": "broken.service",
            },
            {"event": "test_event"},
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    with pytest.raises(exceptions.HomeAssistantError, match="It is not working!"):
        await script_obj.async_run(context=Context())

    assert len(events) == 2

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [
                {
                    "result": {
                        "params": {
                            "domain": "broken",
                            "service": "service",
                            "service_data": {},
                            "target": {},
                        },
                        "running_script": False,
                    },
                }
            ],
            "2": [{"result": {"event": "test_event", "event_data": {}}}],
            "3": [
                {
                    "error_type": HomeAssistantError,
                    "result": {
                        "params": {
                            "domain": "broken",
                            "service": "service",
                            "service_data": {},
                            "target": {},
                        },
                        "running_script": False,
                    },
                }
            ],
        },
        expected_script_execution="error",
    )


async def test_continue_on_error_with_stop(hass: HomeAssistant) -> None:
    """Test continue on error doesn't work with explicit an stop."""
    sequence = cv.SCRIPT_SCHEMA(
        [
            {
                "continue_on_error": True,
                "stop": "Stop it!",
            },
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=Context())

    assert_action_trace(
        {
            "0": [{"result": {"stop": "Stop it!", "error": False}}],
        },
        expected_script_execution="finished",
    )


async def test_continue_on_error_automation_issue(hass: HomeAssistant) -> None:
    """Test continue on error doesn't block action automation errors."""
    sequence = cv.SCRIPT_SCHEMA(
        [
            {
                "continue_on_error": True,
                "service": "service.not_found",
            },
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    with pytest.raises(exceptions.ServiceNotFound):
        await script_obj.async_run(context=Context())

    assert_action_trace(
        {
            "0": [
                {
                    "error_type": ServiceNotFound,
                    "result": {
                        "params": {
                            "domain": "service",
                            "service": "not_found",
                            "service_data": {},
                            "target": {},
                        },
                        "running_script": False,
                    },
                }
            ],
        },
        expected_script_execution="error",
    )


async def test_continue_on_error_unknown_error(hass: HomeAssistant) -> None:
    """Test continue on error doesn't block unknown errors from e.g., libraries."""

    class MyLibraryError(Exception):
        """My custom library error."""

    @callback
    def some_service(service: ServiceCall) -> None:
        """Break this service with an error."""
        raise MyLibraryError("It is not working!")

    hass.services.async_register("some", "service", some_service)

    sequence = cv.SCRIPT_SCHEMA(
        [
            {
                "continue_on_error": True,
                "service": "some.service",
            },
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    with pytest.raises(MyLibraryError):
        await script_obj.async_run(context=Context())

    assert_action_trace(
        {
            "0": [
                {
                    "error_type": MyLibraryError,
                    "result": {
                        "params": {
                            "domain": "some",
                            "service": "service",
                            "service_data": {},
                            "target": {},
                        },
                        "running_script": False,
                    },
                }
            ],
        },
        expected_script_execution="error",
    )


async def test_disabled_actions(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test disabled action steps."""
    events = async_capture_events(hass, "test_event")

    @callback
    def broken_service(service: ServiceCall) -> None:
        """Break this service with an error."""
        raise HomeAssistantError("This service should not be called")

    hass.services.async_register("broken", "service", broken_service)

    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": "test_event"},
            {
                "alias": "Hello",
                "enabled": False,
                "service": "broken.service",
            },
            {"alias": "World", "enabled": False, "event": "test_event"},
            {"event": "test_event"},
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    await script_obj.async_run(context=Context())

    assert len(events) == 2
    assert "Test Name: Skipped disabled step Hello" in caplog.text
    assert "Test Name: Skipped disabled step World" in caplog.text

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"result": {"enabled": False}}],
            "2": [{"result": {"enabled": False}}],
            "3": [{"result": {"event": "test_event", "event_data": {}}}],
        },
    )


async def test_condition_and_shorthand(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if we can use the shorthand and conditions in a script."""
    events = async_capture_events(hass, "test_event")
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": "test_event"},
            {
                "alias": "shorthand and condition",
                "and": [
                    {
                        "condition": "template",
                        "value_template": "{{ states('test.entity') == 'hello' }}",
                    }
                ],
            },
            {"event": "test_event"},
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    hass.states.async_set("test.entity", "hello")
    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert "Test condition shorthand and condition: True" in caplog.text
    assert len(events) == 2

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"result": {"result": True}}],
            "1/conditions/0": [
                {"result": {"entities": ["test.entity"], "result": True}}
            ],
            "2": [{"result": {"event": "test_event", "event_data": {}}}],
        }
    )


async def test_condition_or_shorthand(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if we can use the shorthand or conditions in a script."""
    events = async_capture_events(hass, "test_event")
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": "test_event"},
            {
                "alias": "shorthand or condition",
                "or": [
                    {
                        "condition": "template",
                        "value_template": "{{ states('test.entity') == 'hello' }}",
                    }
                ],
            },
            {"event": "test_event"},
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    hass.states.async_set("test.entity", "hello")
    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert "Test condition shorthand or condition: True" in caplog.text
    assert len(events) == 2

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"result": {"result": True}}],
            "1/conditions/0": [
                {"result": {"entities": ["test.entity"], "result": True}}
            ],
            "2": [{"result": {"event": "test_event", "event_data": {}}}],
        }
    )


async def test_condition_not_shorthand(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if we can use the shorthand not conditions in a script."""
    events = async_capture_events(hass, "test_event")
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"event": "test_event"},
            {
                "alias": "shorthand not condition",
                "not": [
                    {
                        "condition": "template",
                        "value_template": "{{ states('test.entity') == 'hello' }}",
                    }
                ],
            },
            {"event": "test_event"},
        ]
    )
    script_obj = script.Script(hass, sequence, "Test Name", "test_domain")

    hass.states.async_set("test.entity", "not hello")
    await script_obj.async_run(context=Context())
    await hass.async_block_till_done()

    assert "Test condition shorthand not condition: True" in caplog.text
    assert len(events) == 2

    assert_action_trace(
        {
            "0": [{"result": {"event": "test_event", "event_data": {}}}],
            "1": [{"result": {"result": True}}],
            "1/conditions/0": [
                {"result": {"entities": ["test.entity"], "result": False}}
            ],
            "2": [{"result": {"event": "test_event", "event_data": {}}}],
        }
    )
