"""The tests for the Template automation."""
from datetime import timedelta
from unittest import mock

import pytest

import homeassistant.components.automation as automation
from homeassistant.components.template import trigger as template_trigger
from homeassistant.core import Context, callback
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    assert_setup_component,
    async_fire_time_changed,
    async_mock_service,
    mock_component,
)
from tests.components.automation import common


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, "group")
    hass.states.async_set("test.entity", "hello")


async def test_if_fires_on_change_bool(hass, calls):
    """Test for firing on boolean change."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ states.test.entity.state and true }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 1

    await common.async_turn_off(hass)
    await hass.async_block_till_done()

    hass.states.async_set("test.entity", "planet")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_change_str(hass, calls):
    """Test for firing on change."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": '{{ states.test.entity.state and "true" }}',
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_change_str_crazy(hass, calls):
    """Test for firing on change."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": '{{ states.test.entity.state and "TrUE" }}',
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_not_fires_on_change_bool(hass, calls):
    """Test for not firing on boolean change."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ states.test.entity.state and false }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_not_fires_on_change_str(hass, calls):
    """Test for not firing on string change."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "template", "value_template": "true"},
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_not_fires_on_change_str_crazy(hass, calls):
    """Test for not firing on string change."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": '{{ "Anything other than true is false." }}',
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_fires_on_no_change(hass, calls):
    """Test for firing on no change."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "template", "value_template": "{{ true }}"},
                "action": {"service": "test.automation"},
            }
        },
    )

    await hass.async_block_till_done()
    cur_len = len(calls)

    hass.states.async_set("test.entity", "hello")
    await hass.async_block_till_done()
    assert cur_len == len(calls)


async def test_if_fires_on_two_change(hass, calls):
    """Test for firing on two changes."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ states.test.entity.state and true }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # Trigger once
    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Trigger again
    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_change_with_template(hass, calls):
    """Test for firing on change with template."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": '{{ is_state("test.entity", "world") }}',
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_not_fires_on_change_with_template(hass, calls):
    """Test for not firing on change with template."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": '{{ is_state("test.entity", "hello") }}',
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    await hass.async_block_till_done()

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_fires_on_change_with_template_advanced(hass, calls):
    """Test for firing on change with template advanced."""
    context = Context()
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": '{{ is_state("test.entity", "world") }}',
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": "{{ trigger.%s }}"
                        % "}} - {{ trigger.".join(
                            (
                                "platform",
                                "entity_id",
                                "from_state.state",
                                "to_state.state",
                                "for",
                            )
                        )
                    },
                },
            }
        },
    )

    await hass.async_block_till_done()

    hass.states.async_set("test.entity", "world", context=context)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].context.parent_id == context.id
    assert "template - test.entity - hello - world - None" == calls[0].data["some"]


async def test_if_fires_on_no_change_with_template_advanced(hass, calls):
    """Test for firing on no change with template advanced."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": """{%- if is_state("test.entity", "world") -%}
                                        true
                                        {%- else -%}
                                        false
                                        {%- endif -%}""",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # Different state
    hass.states.async_set("test.entity", "worldz")
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Different state
    hass.states.async_set("test.entity", "hello")
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_fires_on_change_with_template_2(hass, calls):
    """Test for firing on change with template."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": '{{ not is_state("test.entity", "world") }}',
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    await hass.async_block_till_done()

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set("test.entity", "home")
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.states.async_set("test.entity", "work")
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.states.async_set("test.entity", "not_home")
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.states.async_set("test.entity", "home")
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_if_action(hass, calls):
    """Test for firing if action."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": [
                    {
                        "condition": "template",
                        "value_template": '{{ is_state("test.entity", "world") }}',
                    }
                ],
                "action": {"service": "test.automation"},
            }
        },
    )

    # Condition is not true yet
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Change condition to true, but it shouldn't be triggered yet
    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Condition is true and event is triggered
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_change_with_bad_template(hass, calls):
    """Test for firing on change with bad template."""
    with assert_setup_component(0, automation.DOMAIN):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {"platform": "template", "value_template": "{{ "},
                    "action": {"service": "test.automation"},
                }
            },
        )


async def test_if_fires_on_change_with_bad_template_2(hass, calls):
    """Test for firing on change with bad template."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ xyz | round(0) }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_wait_template_with_trigger(hass, calls):
    """Test using wait template with 'trigger.entity_id'."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ states.test.entity.state == 'world' }}",
                },
                "action": [
                    {"event": "test_event"},
                    {"wait_template": "{{ is_state(trigger.entity_id, 'hello') }}"},
                    {
                        "service": "test.automation",
                        "data_template": {
                            "some": "{{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                (
                                    "platform",
                                    "entity_id",
                                    "from_state.state",
                                    "to_state.state",
                                    "for",
                                )
                            )
                        },
                    },
                ],
            }
        },
    )

    await hass.async_block_till_done()

    @callback
    def event_handler(event):
        hass.states.async_set("test.entity", "hello")

    hass.bus.async_listen_once("test_event", event_handler)

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "template - test.entity - hello - world - None"


async def test_if_fires_on_change_with_for(hass, calls):
    """Test for firing on change with for."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": {"seconds": 5},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_change_with_for_advanced(hass, calls):
    """Test for firing on change with for advanced."""
    context = Context()
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": '{{ is_state("test.entity", "world") }}',
                    "for": {"seconds": 5},
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": "{{ trigger.%s }}"
                        % "}} - {{ trigger.".join(
                            (
                                "platform",
                                "entity_id",
                                "from_state.state",
                                "to_state.state",
                                "for",
                            )
                        )
                    },
                },
            }
        },
    )

    await hass.async_block_till_done()

    hass.states.async_set("test.entity", "world", context=context)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].context.parent_id == context.id
    assert "template - test.entity - hello - world - 0:00:05" == calls[0].data["some"]


async def test_if_fires_on_change_with_for_0(hass, calls):
    """Test for firing on change with for: 0."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": {"seconds": 0},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_change_with_for_0_advanced(hass, calls):
    """Test for firing on change with for: 0 advanced."""
    context = Context()
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": '{{ is_state("test.entity", "world") }}',
                    "for": {"seconds": 0},
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": "{{ trigger.%s }}"
                        % "}} - {{ trigger.".join(
                            (
                                "platform",
                                "entity_id",
                                "from_state.state",
                                "to_state.state",
                                "for",
                            )
                        )
                    },
                },
            }
        },
    )

    await hass.async_block_till_done()

    hass.states.async_set("test.entity", "world", context=context)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].context.parent_id == context.id
    assert calls[0].data["some"] == "template - test.entity - hello - world - 0:00:00"


async def test_if_fires_on_change_with_for_2(hass, calls):
    """Test for firing on change with for."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": 5,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_not_fires_on_change_with_for(hass, calls):
    """Test for firing on change with for."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": {"seconds": 5},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=4))
    await hass.async_block_till_done()
    assert len(calls) == 0
    hass.states.async_set("test.entity", "hello")
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_not_fires_when_turned_off_with_for(hass, calls):
    """Test for firing on change with for."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": {"seconds": 5},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=4))
    await hass.async_block_till_done()
    assert len(calls) == 0
    await common.async_turn_off(hass)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_fires_on_change_with_for_template_1(hass, calls):
    """Test for firing on change with for template."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": {"seconds": "{{ 5 }}"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_change_with_for_template_2(hass, calls):
    """Test for firing on change with for template."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": "{{ 5 }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_change_with_for_template_3(hass, calls):
    """Test for firing on change with for template."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": "00:00:{{ 5 }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_invalid_for_template_1(hass, calls):
    """Test for invalid for template."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": {"seconds": "{{ five }}"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    with mock.patch.object(template_trigger, "_LOGGER") as mock_logger:
        hass.states.async_set("test.entity", "world")
        await hass.async_block_till_done()
        assert mock_logger.error.called
