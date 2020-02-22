"""The tests for the Script component."""
# pylint: disable=protected-access
from datetime import timedelta
import functools as ft
from unittest import mock

import asynctest
import jinja2
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


async def test_firing_event(hass):
    """Test the firing of events."""
    event = "test_event"
    context = Context()
    calls = []

    @callback
    def record_event(event):
        """Add recorded event to set."""
        calls.append(event)

    hass.bus.async_listen(event, record_event)

    script_obj = script.Script(
        hass, cv.SCRIPT_SCHEMA({"event": event, "event_data": {"hello": "world"}})
    )

    await script_obj.async_run(context=context)

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].context is context
    assert calls[0].data.get("hello") == "world"
    assert not script_obj.can_cancel


async def test_firing_event_template(hass):
    """Test the firing of events."""
    event = "test_event"
    context = Context()
    calls = []

    @callback
    def record_event(event):
        """Add recorded event to set."""
        calls.append(event)

    hass.bus.async_listen(event, record_event)

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
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
        ),
    )

    await script_obj.async_run({"is_world": "yes"}, context=context)

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].context is context
    assert calls[0].data == {
        "dict": {1: "yes", 2: "yesyes", 3: "yesyesyes"},
        "list": ["yes", "yesyes"],
    }
    assert not script_obj.can_cancel


async def test_calling_service(hass):
    """Test the calling of a service."""
    calls = []
    context = Context()

    @callback
    def record_call(service):
        """Add recorded event to set."""
        calls.append(service)

    hass.services.async_register("test", "script", record_call)

    hass.async_add_job(
        ft.partial(
            script.call_from_config,
            hass,
            {"service": "test.script", "data": {"hello": "world"}},
            context=context,
        )
    )

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].context is context
    assert calls[0].data.get("hello") == "world"


async def test_activating_scene(hass):
    """Test the activation of a scene."""
    calls = []
    context = Context()

    @callback
    def record_call(service):
        """Add recorded event to set."""
        calls.append(service)

    hass.services.async_register(scene.DOMAIN, SERVICE_TURN_ON, record_call)

    hass.async_add_job(
        ft.partial(
            script.call_from_config, hass, {"scene": "scene.hello"}, context=context
        )
    )

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].context is context
    assert calls[0].data.get(ATTR_ENTITY_ID) == "scene.hello"


async def test_calling_service_template(hass):
    """Test the calling of a service."""
    calls = []
    context = Context()

    @callback
    def record_call(service):
        """Add recorded event to set."""
        calls.append(service)

    hass.services.async_register("test", "script", record_call)

    hass.async_add_job(
        ft.partial(
            script.call_from_config,
            hass,
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
            },
            {"is_world": "yes"},
            context=context,
        )
    )

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].context is context
    assert calls[0].data.get("hello") == "world"


async def test_delay(hass):
    """Test the delay."""
    event = "test_event"
    events = []
    context = Context()
    delay_alias = "delay step"

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event},
                {"delay": {"seconds": 5}, "alias": delay_alias},
                {"event": event},
            ]
        ),
    )

    await script_obj.async_run(context=context)
    await hass.async_block_till_done()

    assert script_obj.is_running
    assert script_obj.can_cancel
    assert script_obj.last_action == delay_alias
    assert len(events) == 1

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert not script_obj.is_running
    assert len(events) == 2
    assert events[0].context is context
    assert events[1].context is context


async def test_delay_template(hass):
    """Test the delay as a template."""
    event = "test_event"
    events = []
    delay_alias = "delay step"

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event},
                {"delay": "00:00:{{ 5 }}", "alias": delay_alias},
                {"event": event},
            ]
        ),
    )

    await script_obj.async_run()
    await hass.async_block_till_done()

    assert script_obj.is_running
    assert script_obj.can_cancel
    assert script_obj.last_action == delay_alias
    assert len(events) == 1

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert not script_obj.is_running
    assert len(events) == 2


async def test_delay_invalid_template(hass):
    """Test the delay as a template that fails."""
    event = "test_event"
    events = []

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event},
                {"delay": "{{ invalid_delay }}"},
                {"delay": {"seconds": 5}},
                {"event": event},
            ]
        ),
    )

    with mock.patch.object(script, "_LOGGER") as mock_logger:
        await script_obj.async_run()
        await hass.async_block_till_done()
        assert mock_logger.error.called

    assert not script_obj.is_running
    assert len(events) == 1


async def test_delay_complex_template(hass):
    """Test the delay with a working complex template."""
    event = "test_event"
    events = []
    delay_alias = "delay step"

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event},
                {"delay": {"seconds": "{{ 5 }}"}, "alias": delay_alias},
                {"event": event},
            ]
        ),
    )

    await script_obj.async_run()
    await hass.async_block_till_done()

    assert script_obj.is_running
    assert script_obj.can_cancel
    assert script_obj.last_action == delay_alias
    assert len(events) == 1

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert not script_obj.is_running
    assert len(events) == 2


async def test_delay_complex_invalid_template(hass):
    """Test the delay with a complex template that fails."""
    event = "test_event"
    events = []

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event},
                {"delay": {"seconds": "{{ invalid_delay }}"}},
                {"delay": {"seconds": "{{ 5 }}"}},
                {"event": event},
            ]
        ),
    )

    with mock.patch.object(script, "_LOGGER") as mock_logger:
        await script_obj.async_run()
        await hass.async_block_till_done()
        assert mock_logger.error.called

    assert not script_obj.is_running
    assert len(events) == 1


async def test_cancel_while_delay(hass):
    """Test the cancelling while the delay is present."""
    event = "test_event"
    events = []

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    script_obj = script.Script(
        hass, cv.SCRIPT_SCHEMA([{"delay": {"seconds": 5}}, {"event": event}])
    )

    await script_obj.async_run()
    await hass.async_block_till_done()

    assert script_obj.is_running
    assert len(events) == 0

    script_obj.async_stop()

    assert not script_obj.is_running

    # Make sure the script is really stopped.
    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert not script_obj.is_running
    assert len(events) == 0


async def test_wait_template(hass):
    """Test the wait template."""
    event = "test_event"
    events = []
    context = Context()
    wait_alias = "wait step"

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    hass.states.async_set("switch.test", "on")

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event},
                {
                    "wait_template": "{{states.switch.test.state == 'off'}}",
                    "alias": wait_alias,
                },
                {"event": event},
            ]
        ),
    )

    await script_obj.async_run(context=context)
    await hass.async_block_till_done()

    assert script_obj.is_running
    assert script_obj.can_cancel
    assert script_obj.last_action == wait_alias
    assert len(events) == 1

    hass.states.async_set("switch.test", "off")
    await hass.async_block_till_done()

    assert not script_obj.is_running
    assert len(events) == 2
    assert events[0].context is context
    assert events[1].context is context


async def test_wait_template_cancel(hass):
    """Test the wait template cancel action."""
    event = "test_event"
    events = []
    wait_alias = "wait step"

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    hass.states.async_set("switch.test", "on")

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event},
                {
                    "wait_template": "{{states.switch.test.state == 'off'}}",
                    "alias": wait_alias,
                },
                {"event": event},
            ]
        ),
    )

    await script_obj.async_run()
    await hass.async_block_till_done()

    assert script_obj.is_running
    assert script_obj.can_cancel
    assert script_obj.last_action == wait_alias
    assert len(events) == 1

    script_obj.async_stop()

    assert not script_obj.is_running
    assert len(events) == 1

    hass.states.async_set("switch.test", "off")
    await hass.async_block_till_done()

    assert not script_obj.is_running
    assert len(events) == 1


async def test_wait_template_not_schedule(hass):
    """Test the wait template with correct condition."""
    event = "test_event"
    events = []

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    hass.states.async_set("switch.test", "on")

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event},
                {"wait_template": "{{states.switch.test.state == 'on'}}"},
                {"event": event},
            ]
        ),
    )

    await script_obj.async_run()
    await hass.async_block_till_done()

    assert not script_obj.is_running
    assert script_obj.can_cancel
    assert len(events) == 2


async def test_wait_template_timeout_halt(hass):
    """Test the wait template, halt on timeout."""
    event = "test_event"
    events = []
    wait_alias = "wait step"

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    hass.states.async_set("switch.test", "on")

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event},
                {
                    "wait_template": "{{states.switch.test.state == 'off'}}",
                    "continue_on_timeout": False,
                    "timeout": 5,
                    "alias": wait_alias,
                },
                {"event": event},
            ]
        ),
    )

    await script_obj.async_run()
    await hass.async_block_till_done()

    assert script_obj.is_running
    assert script_obj.can_cancel
    assert script_obj.last_action == wait_alias
    assert len(events) == 1

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert not script_obj.is_running
    assert len(events) == 1


async def test_wait_template_timeout_continue(hass):
    """Test the wait template with continuing the script."""
    event = "test_event"
    events = []
    wait_alias = "wait step"

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    hass.states.async_set("switch.test", "on")

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event},
                {
                    "wait_template": "{{states.switch.test.state == 'off'}}",
                    "timeout": 5,
                    "continue_on_timeout": True,
                    "alias": wait_alias,
                },
                {"event": event},
            ]
        ),
    )

    await script_obj.async_run()
    await hass.async_block_till_done()

    assert script_obj.is_running
    assert script_obj.can_cancel
    assert script_obj.last_action == wait_alias
    assert len(events) == 1

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert not script_obj.is_running
    assert len(events) == 2


async def test_wait_template_timeout_default(hass):
    """Test the wait template with default contiune."""
    event = "test_event"
    events = []
    wait_alias = "wait step"

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    hass.states.async_set("switch.test", "on")

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event},
                {
                    "wait_template": "{{states.switch.test.state == 'off'}}",
                    "timeout": 5,
                    "alias": wait_alias,
                },
                {"event": event},
            ]
        ),
    )

    await script_obj.async_run()
    await hass.async_block_till_done()

    assert script_obj.is_running
    assert script_obj.can_cancel
    assert script_obj.last_action == wait_alias
    assert len(events) == 1

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert not script_obj.is_running
    assert len(events) == 2


async def test_wait_template_variables(hass):
    """Test the wait template with variables."""
    event = "test_event"
    events = []
    wait_alias = "wait step"

    @callback
    def record_event(event):
        """Add recorded event to set."""
        events.append(event)

    hass.bus.async_listen(event, record_event)

    hass.states.async_set("switch.test", "on")

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"event": event},
                {"wait_template": "{{is_state(data, 'off')}}", "alias": wait_alias},
                {"event": event},
            ]
        ),
    )

    await script_obj.async_run({"data": "switch.test"})
    await hass.async_block_till_done()

    assert script_obj.is_running
    assert script_obj.can_cancel
    assert script_obj.last_action == wait_alias
    assert len(events) == 1

    hass.states.async_set("switch.test", "off")
    await hass.async_block_till_done()

    assert not script_obj.is_running
    assert len(events) == 2


async def test_passing_variables_to_script(hass):
    """Test if we can pass variables to script."""
    calls = []

    @callback
    def record_call(service):
        """Add recorded event to set."""
        calls.append(service)

    hass.services.async_register("test", "script", record_call)

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {
                    "service": "test.script",
                    "data_template": {"hello": "{{ greeting }}"},
                },
                {"delay": "{{ delay_period }}"},
                {
                    "service": "test.script",
                    "data_template": {"hello": "{{ greeting2 }}"},
                },
            ]
        ),
    )

    await script_obj.async_run(
        {"greeting": "world", "greeting2": "universe", "delay_period": "00:00:05"}
    )

    await hass.async_block_till_done()

    assert script_obj.is_running
    assert len(calls) == 1
    assert calls[-1].data["hello"] == "world"

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert not script_obj.is_running
    assert len(calls) == 2
    assert calls[-1].data["hello"] == "universe"


async def test_condition(hass):
    """Test if we can use conditions in a script."""
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


async def test_all_conditions_cached(hass):
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

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [{"event": event}, {"delay": {"seconds": 5}}, {"event": event}]
        ),
    )

    assert script_obj.last_triggered is None

    time = dt_util.utcnow()
    with mock.patch("homeassistant.helpers.script.date_util.utcnow", return_value=time):
        await script_obj.async_run()
        await hass.async_block_till_done()

    assert script_obj.last_triggered == time


async def test_propagate_error_service_not_found(hass):
    """Test that a script aborts when a service is not found."""
    events = []

    @callback
    def record_event(event):
        events.append(event)

    hass.bus.async_listen("test_event", record_event)

    script_obj = script.Script(
        hass, cv.SCRIPT_SCHEMA([{"service": "test.script"}, {"event": "test_event"}])
    )

    with pytest.raises(exceptions.ServiceNotFound):
        await script_obj.async_run()

    assert len(events) == 0
    assert script_obj._cur == -1


async def test_propagate_error_invalid_service_data(hass):
    """Test that a script aborts when we send invalid service data."""
    events = []

    @callback
    def record_event(event):
        events.append(event)

    hass.bus.async_listen("test_event", record_event)

    calls = []

    @callback
    def record_call(service):
        """Add recorded event to set."""
        calls.append(service)

    hass.services.async_register(
        "test", "script", record_call, schema=vol.Schema({"text": str})
    )

    script_obj = script.Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [{"service": "test.script", "data": {"text": 1}}, {"event": "test_event"}]
        ),
    )

    with pytest.raises(vol.Invalid):
        await script_obj.async_run()

    assert len(events) == 0
    assert len(calls) == 0
    assert script_obj._cur == -1


async def test_propagate_error_service_exception(hass):
    """Test that a script aborts when a service throws an exception."""
    events = []

    @callback
    def record_event(event):
        events.append(event)

    hass.bus.async_listen("test_event", record_event)

    calls = []

    @callback
    def record_call(service):
        """Add recorded event to set."""
        raise ValueError("BROKEN")

    hass.services.async_register("test", "script", record_call)

    script_obj = script.Script(
        hass, cv.SCRIPT_SCHEMA([{"service": "test.script"}, {"event": "test_event"}])
    )

    with pytest.raises(ValueError):
        await script_obj.async_run()

    assert len(events) == 0
    assert len(calls) == 0
    assert script_obj._cur == -1


def test_log_exception():
    """Test logged output."""
    script_obj = script.Script(
        None, cv.SCRIPT_SCHEMA([{"service": "test.script"}, {"event": "test_event"}])
    )
    script_obj._exception_step = 1

    for exc, msg in (
        (vol.Invalid("Invalid number"), "Invalid data"),
        (
            exceptions.TemplateError(jinja2.TemplateError("Unclosed bracket")),
            "Error rendering template",
        ),
        (exceptions.Unauthorized(), "Unauthorized"),
        (exceptions.ServiceNotFound("light", "turn_on"), "Service not found"),
        (ValueError("Cannot parse JSON"), "Unknown error"),
    ):
        logger = mock.Mock()
        script_obj.async_log_exception(logger, "Test error", exc)

        assert len(logger.mock_calls) == 1
        _, _, p_error_desc, p_action_type, p_step, p_error = logger.mock_calls[0][1]

        assert p_error_desc == msg
        assert p_action_type == script.ACTION_FIRE_EVENT
        assert p_step == 2
        if isinstance(exc, ValueError):
            assert p_error == ""
        else:
            assert p_error == str(exc)


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
