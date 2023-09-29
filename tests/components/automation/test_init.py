"""The tests for the automation component."""
import asyncio
from datetime import timedelta
import logging
from unittest.mock import Mock, patch

import pytest

import homeassistant.components.automation as automation
from homeassistant.components.automation import (
    ATTR_SOURCE,
    DOMAIN,
    EVENT_AUTOMATION_RELOADED,
    EVENT_AUTOMATION_TRIGGERED,
    SERVICE_TRIGGER,
    AutomationEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
    EVENT_HOMEASSISTANT_STARTED,
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import (
    Context,
    CoreState,
    HomeAssistant,
    ServiceCall,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers.script import (
    SCRIPT_MODE_CHOICES,
    SCRIPT_MODE_PARALLEL,
    SCRIPT_MODE_QUEUED,
    SCRIPT_MODE_RESTART,
    SCRIPT_MODE_SINGLE,
    _async_stop_scripts_at_shutdown,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml
import homeassistant.util.dt as dt_util

from tests.common import (
    MockUser,
    assert_setup_component,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
    mock_restore_cache,
)
from tests.components.logbook.common import MockRow, mock_humanify
from tests.components.repairs import get_repairs
from tests.typing import WebSocketGenerator


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_service_data_not_a_dict(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, calls
) -> None:
    """Test service data not dict."""
    with assert_setup_component(1, automation.DOMAIN):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": {"service": "test.automation", "data": 100},
                }
            },
        )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 0
    assert "Result is not a Dictionary" in caplog.text


async def test_service_data_single_template(hass: HomeAssistant, calls) -> None:
    """Test service data not dict."""
    with assert_setup_component(1, automation.DOMAIN):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": {
                        "service": "test.automation",
                        "data": "{{ { 'foo': 'bar' } }}",
                    },
                }
            },
        )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["foo"] == "bar"


async def test_service_specify_data(hass: HomeAssistant, calls) -> None:
    """Test service data."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": (
                            "{{ trigger.platform }} - {{ trigger.event.event_type }}"
                        )
                    },
                },
            }
        },
    )

    time = dt_util.utcnow()

    with patch("homeassistant.helpers.script.utcnow", return_value=time):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "event - test_event"
    state = hass.states.get("automation.hello")
    assert state is not None
    assert state.attributes.get("last_triggered") == time


async def test_service_specify_entity_id(hass: HomeAssistant, calls) -> None:
    """Test service data."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert ["hello.world"] == calls[0].data.get(ATTR_ENTITY_ID)


async def test_service_specify_entity_id_list(hass: HomeAssistant, calls) -> None:
    """Test service data."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {
                    "service": "test.automation",
                    "entity_id": ["hello.world", "hello.world2"],
                },
            }
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert ["hello.world", "hello.world2"] == calls[0].data.get(ATTR_ENTITY_ID)


async def test_two_triggers(hass: HomeAssistant, calls) -> None:
    """Test triggers."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": [
                    {"platform": "event", "event_type": "test_event"},
                    {"platform": "state", "entity_id": "test.entity"},
                ],
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1
    hass.states.async_set("test.entity", "hello")
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_trigger_service_ignoring_condition(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, calls
) -> None:
    """Test triggers."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "test",
                "trigger": [{"platform": "event", "event_type": "test_event"}],
                "condition": {
                    "condition": "numeric_state",
                    "entity_id": "non.existing",
                    "above": "1",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    caplog.clear()
    caplog.set_level(logging.WARNING)

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 0

    assert len(caplog.record_tuples) == 1
    assert caplog.record_tuples[0][1] == logging.WARNING

    await hass.services.async_call(
        "automation", "trigger", {"entity_id": "automation.test"}, blocking=True
    )
    assert len(calls) == 1

    await hass.services.async_call(
        "automation",
        "trigger",
        {"entity_id": "automation.test", "skip_condition": True},
        blocking=True,
    )
    assert len(calls) == 2

    await hass.services.async_call(
        "automation",
        "trigger",
        {"entity_id": "automation.test", "skip_condition": False},
        blocking=True,
    )
    assert len(calls) == 2


async def test_two_conditions_with_and(hass: HomeAssistant, calls) -> None:
    """Test two and conditions."""
    entity_id = "test.entity"
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": [{"platform": "event", "event_type": "test_event"}],
                "condition": [
                    {"condition": "state", "entity_id": entity_id, "state": "100"},
                    {
                        "condition": "numeric_state",
                        "entity_id": entity_id,
                        "below": 150,
                    },
                ],
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(entity_id, 100)
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.states.async_set(entity_id, 101)
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.states.async_set(entity_id, 151)
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_shorthand_conditions_template(hass: HomeAssistant, calls) -> None:
    """Test shorthand nation form in conditions."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": [{"platform": "event", "event_type": "test_event"}],
                "condition": "{{ is_state('test.entity', 'hello') }}",
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "hello")
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.states.async_set("test.entity", "goodbye")
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_automation_list_setting(hass: HomeAssistant, calls) -> None:
    """Event is not a valid condition."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": {"service": "test.automation"},
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event_2"},
                    "action": {"service": "test.automation"},
                },
            ]
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.bus.async_fire("test_event_2")
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_automation_calling_two_actions(hass: HomeAssistant, calls) -> None:
    """Test if we can call two actions from automation async definition."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": [
                    {"service": "test.automation", "data": {"position": 0}},
                    {"service": "test.automation", "data": {"position": 1}},
                ],
            }
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()

    assert len(calls) == 2
    assert calls[0].data["position"] == 0
    assert calls[1].data["position"] == 1


async def test_shared_context(hass: HomeAssistant, calls) -> None:
    """Test that the shared context is passed down the chain."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "alias": "hello",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": {"event": "test_event2"},
                },
                {
                    "alias": "bye",
                    "trigger": {"platform": "event", "event_type": "test_event2"},
                    "action": {"service": "test.automation"},
                },
            ]
        },
    )

    context = Context()
    first_automation_listener = Mock()
    event_mock = Mock()

    hass.bus.async_listen("test_event2", first_automation_listener)
    hass.bus.async_listen(EVENT_AUTOMATION_TRIGGERED, event_mock)
    hass.bus.async_fire("test_event", context=context)
    await hass.async_block_till_done()

    # Ensure events was fired
    assert first_automation_listener.call_count == 1
    assert event_mock.call_count == 2

    # Verify automation triggered evenet for 'hello' automation
    args, _ = event_mock.call_args_list[0]
    first_trigger_context = args[0].context
    assert first_trigger_context.parent_id == context.id
    # Ensure event data has all attributes set
    assert args[0].data.get(ATTR_NAME) is not None
    assert args[0].data.get(ATTR_ENTITY_ID) is not None
    assert args[0].data.get(ATTR_SOURCE) is not None

    # Ensure context set correctly for event fired by 'hello' automation
    args, _ = first_automation_listener.call_args
    assert args[0].context is first_trigger_context

    # Ensure the 'hello' automation state has the right context
    state = hass.states.get("automation.hello")
    assert state is not None
    assert state.context is first_trigger_context

    # Verify automation triggered evenet for 'bye' automation
    args, _ = event_mock.call_args_list[1]
    second_trigger_context = args[0].context
    assert second_trigger_context.parent_id == first_trigger_context.id
    # Ensure event data has all attributes set
    assert args[0].data.get(ATTR_NAME) is not None
    assert args[0].data.get(ATTR_ENTITY_ID) is not None
    assert args[0].data.get(ATTR_SOURCE) is not None

    # Ensure the service call from the second automation
    # shares the same context
    assert len(calls) == 1
    assert calls[0].context is second_trigger_context


async def test_services(hass: HomeAssistant, calls) -> None:
    """Test the automation services for turning entities on/off."""
    entity_id = "automation.hello"

    assert hass.states.get(entity_id) is None
    assert not automation.is_on(hass, entity_id)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation"},
            }
        },
    )

    assert hass.states.get(entity_id) is not None
    assert automation.is_on(hass, entity_id)

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    assert not automation.is_on(hass, entity_id)
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1

    await hass.services.async_call(
        automation.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert automation.is_on(hass, entity_id)
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 2

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert not automation.is_on(hass, entity_id)
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 2

    await hass.services.async_call(
        automation.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.services.async_call(
        automation.DOMAIN, SERVICE_TRIGGER, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert len(calls) == 3

    await hass.services.async_call(
        automation.DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.services.async_call(
        automation.DOMAIN, SERVICE_TRIGGER, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert len(calls) == 4

    await hass.services.async_call(
        automation.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert automation.is_on(hass, entity_id)


async def test_reload_config_service(
    hass: HomeAssistant, calls, hass_admin_user: MockUser, hass_read_only_user: MockUser
) -> None:
    """Test the reload config service."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {
                    "service": "test.automation",
                    "data_template": {"event": "{{ trigger.event.event_type }}"},
                },
            }
        },
    )
    assert hass.states.get("automation.hello") is not None
    assert hass.states.get("automation.bye") is None
    listeners = hass.bus.async_listeners()
    assert listeners.get("test_event") == 1
    assert listeners.get("test_event2") is None

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data.get("event") == "test_event"

    test_reload_event = async_capture_events(hass, EVENT_AUTOMATION_RELOADED)

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            automation.DOMAIN: {
                "alias": "bye",
                "trigger": {"platform": "event", "event_type": "test_event2"},
                "action": {
                    "service": "test.automation",
                    "data_template": {"event": "{{ trigger.event.event_type }}"},
                },
            }
        },
    ):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(
                automation.DOMAIN,
                SERVICE_RELOAD,
                context=Context(user_id=hass_read_only_user.id),
                blocking=True,
            )
        await hass.services.async_call(
            automation.DOMAIN,
            SERVICE_RELOAD,
            context=Context(user_id=hass_admin_user.id),
            blocking=True,
        )
        # De-flake ?!
        await hass.async_block_till_done()

    assert len(test_reload_event) == 1

    assert hass.states.get("automation.hello") is None
    assert hass.states.get("automation.bye") is not None
    listeners = hass.bus.async_listeners()
    assert listeners.get("test_event") is None
    assert listeners.get("test_event2") == 1

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data.get("event") == "test_event2"


async def test_reload_config_when_invalid_config(hass: HomeAssistant, calls) -> None:
    """Test the reload config service handling invalid config."""
    with assert_setup_component(1, automation.DOMAIN):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "alias": "hello",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": {
                        "service": "test.automation",
                        "data_template": {"event": "{{ trigger.event.event_type }}"},
                    },
                }
            },
        )
    assert hass.states.get("automation.hello") is not None

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data.get("event") == "test_event"

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={automation.DOMAIN: "not valid"},
    ):
        await hass.services.async_call(automation.DOMAIN, SERVICE_RELOAD, blocking=True)

    assert hass.states.get("automation.hello") is None

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_reload_config_handles_load_fails(hass: HomeAssistant, calls) -> None:
    """Test the reload config service."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {
                    "service": "test.automation",
                    "data_template": {"event": "{{ trigger.event.event_type }}"},
                },
            }
        },
    )
    assert hass.states.get("automation.hello") is not None

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data.get("event") == "test_event"

    with patch(
        "homeassistant.config.load_yaml_config_file",
        side_effect=HomeAssistantError("bla"),
    ):
        await hass.services.async_call(automation.DOMAIN, SERVICE_RELOAD, blocking=True)

    assert hass.states.get("automation.hello") is not None

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 2


@pytest.mark.parametrize("service", ["turn_off_stop", "turn_off_no_stop", "reload"])
async def test_automation_stops(hass: HomeAssistant, calls, service) -> None:
    """Test that turning off / reloading stops any running actions as appropriate."""
    entity_id = "automation.hello"
    test_entity = "test.entity"

    config = {
        automation.DOMAIN: {
            "alias": "hello",
            "trigger": {"platform": "event", "event_type": "test_event"},
            "action": [
                {"event": "running"},
                {"wait_template": "{{ is_state('test.entity', 'goodbye') }}"},
                {"service": "test.automation"},
            ],
        }
    }
    assert await async_setup_component(hass, automation.DOMAIN, config)

    running = asyncio.Event()

    @callback
    def running_cb(event):
        running.set()

    hass.bus.async_listen_once("running", running_cb)
    hass.states.async_set(test_entity, "hello")

    hass.bus.async_fire("test_event")
    await running.wait()

    if service == "turn_off_stop":
        await hass.services.async_call(
            automation.DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    elif service == "turn_off_no_stop":
        await hass.services.async_call(
            automation.DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id, automation.CONF_STOP_ACTIONS: False},
            blocking=True,
        )
    else:
        config[automation.DOMAIN]["alias"] = "goodbye"
        with patch(
            "homeassistant.config.load_yaml_config_file",
            autospec=True,
            return_value=config,
        ):
            await hass.services.async_call(
                automation.DOMAIN, SERVICE_RELOAD, blocking=True
            )

    hass.states.async_set(test_entity, "goodbye")
    await hass.async_block_till_done()

    assert len(calls) == (1 if service == "turn_off_no_stop" else 0)


@pytest.mark.parametrize("extra_config", ({}, {"id": "sun"}))
async def test_reload_unchanged_does_not_stop(
    hass: HomeAssistant, calls, extra_config
) -> None:
    """Test that reloading stops any running actions as appropriate."""
    test_entity = "test.entity"

    config = {
        automation.DOMAIN: {
            "alias": "hello",
            "trigger": {"platform": "event", "event_type": "test_event"},
            "action": [
                {"event": "running"},
                {"wait_template": "{{ is_state('test.entity', 'goodbye') }}"},
                {"service": "test.automation"},
            ],
        }
    }
    config[automation.DOMAIN].update(**extra_config)
    assert await async_setup_component(hass, automation.DOMAIN, config)

    running = asyncio.Event()

    @callback
    def running_cb(event):
        running.set()

    hass.bus.async_listen_once("running", running_cb)
    hass.states.async_set(test_entity, "hello")

    hass.bus.async_fire("test_event")
    await running.wait()
    assert len(calls) == 0

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=config,
    ):
        await hass.services.async_call(automation.DOMAIN, SERVICE_RELOAD, blocking=True)

    hass.states.async_set(test_entity, "goodbye")
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_reload_moved_automation_without_alias(
    hass: HomeAssistant, calls
) -> None:
    """Test that changing the order of automations without alias triggers reload."""
    with patch(
        "homeassistant.components.automation.AutomationEntity", wraps=AutomationEntity
    ) as automation_entity_init:
        config = {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": [{"service": "test.automation"}],
                },
                {
                    "alias": "automation_with_alias",
                    "trigger": {"platform": "event", "event_type": "test_event2"},
                    "action": [{"service": "test.automation"}],
                },
            ]
        }
        assert await async_setup_component(hass, automation.DOMAIN, config)
        assert automation_entity_init.call_count == 2
        automation_entity_init.reset_mock()

        assert hass.states.get("automation.automation_0")
        assert not hass.states.get("automation.automation_1")
        assert hass.states.get("automation.automation_with_alias")

        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

        # Reverse the order of the automations
        config[automation.DOMAIN].reverse()
        with patch(
            "homeassistant.config.load_yaml_config_file",
            autospec=True,
            return_value=config,
        ):
            await hass.services.async_call(
                automation.DOMAIN, SERVICE_RELOAD, blocking=True
            )

        assert automation_entity_init.call_count == 1
        automation_entity_init.reset_mock()

        assert not hass.states.get("automation.automation_0")
        assert hass.states.get("automation.automation_1")
        assert hass.states.get("automation.automation_with_alias")

        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2


async def test_reload_identical_automations_without_id(
    hass: HomeAssistant, calls
) -> None:
    """Test reloading of identical automations without id."""
    with patch(
        "homeassistant.components.automation.AutomationEntity", wraps=AutomationEntity
    ) as automation_entity_init:
        config = {
            automation.DOMAIN: [
                {
                    "alias": "dolly",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": [{"service": "test.automation"}],
                },
                {
                    "alias": "dolly",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": [{"service": "test.automation"}],
                },
                {
                    "alias": "dolly",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": [{"service": "test.automation"}],
                },
            ]
        }
        assert await async_setup_component(hass, automation.DOMAIN, config)
        assert automation_entity_init.call_count == 3
        automation_entity_init.reset_mock()

        assert hass.states.get("automation.dolly")
        assert hass.states.get("automation.dolly_2")
        assert hass.states.get("automation.dolly_3")

        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 3

        # Reload the automations without any change
        with patch(
            "homeassistant.config.load_yaml_config_file",
            autospec=True,
            return_value=config,
        ):
            await hass.services.async_call(
                automation.DOMAIN, SERVICE_RELOAD, blocking=True
            )

        assert automation_entity_init.call_count == 0
        automation_entity_init.reset_mock()

        assert hass.states.get("automation.dolly")
        assert hass.states.get("automation.dolly_2")
        assert hass.states.get("automation.dolly_3")

        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 6

        # Remove two clones
        del config[automation.DOMAIN][-1]
        del config[automation.DOMAIN][-1]
        with patch(
            "homeassistant.config.load_yaml_config_file",
            autospec=True,
            return_value=config,
        ):
            await hass.services.async_call(
                automation.DOMAIN, SERVICE_RELOAD, blocking=True
            )

        assert automation_entity_init.call_count == 0
        automation_entity_init.reset_mock()

        assert hass.states.get("automation.dolly")

        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 7

        # Add two clones
        config[automation.DOMAIN].append(config[automation.DOMAIN][-1])
        config[automation.DOMAIN].append(config[automation.DOMAIN][-1])
        with patch(
            "homeassistant.config.load_yaml_config_file",
            autospec=True,
            return_value=config,
        ):
            await hass.services.async_call(
                automation.DOMAIN, SERVICE_RELOAD, blocking=True
            )

        assert automation_entity_init.call_count == 2
        automation_entity_init.reset_mock()

        assert hass.states.get("automation.dolly")
        assert hass.states.get("automation.dolly_2")
        assert hass.states.get("automation.dolly_3")

        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 10


@pytest.mark.parametrize(
    "automation_config",
    (
        {
            "trigger": {"platform": "event", "event_type": "test_event"},
            "action": [{"service": "test.automation"}],
        },
        # An automation using templates
        {
            "trigger": {"platform": "event", "event_type": "test_event"},
            "action": [{"service": "{{ 'test.automation' }}"}],
        },
        # An automation using blueprint
        {
            "use_blueprint": {
                "path": "test_event_service.yaml",
                "input": {
                    "trigger_event": "test_event",
                    "service_to_call": "test.automation",
                    "a_number": 5,
                },
            }
        },
        # An automation using blueprint with templated input
        {
            "use_blueprint": {
                "path": "test_event_service.yaml",
                "input": {
                    "trigger_event": "{{ 'test_event' }}",
                    "service_to_call": "{{ 'test.automation' }}",
                    "a_number": 5,
                },
            }
        },
        {
            "id": "sun",
            "trigger": {"platform": "event", "event_type": "test_event"},
            "action": [{"service": "test.automation"}],
        },
        # An automation using templates
        {
            "id": "sun",
            "trigger": {"platform": "event", "event_type": "test_event"},
            "action": [{"service": "{{ 'test.automation' }}"}],
        },
        # An automation using blueprint
        {
            "id": "sun",
            "use_blueprint": {
                "path": "test_event_service.yaml",
                "input": {
                    "trigger_event": "test_event",
                    "service_to_call": "test.automation",
                    "a_number": 5,
                },
            },
        },
        # An automation using blueprint with templated input
        {
            "id": "sun",
            "use_blueprint": {
                "path": "test_event_service.yaml",
                "input": {
                    "trigger_event": "{{ 'test_event' }}",
                    "service_to_call": "{{ 'test.automation' }}",
                    "a_number": 5,
                },
            },
        },
    ),
)
async def test_reload_unchanged_automation(
    hass: HomeAssistant, calls, automation_config
) -> None:
    """Test an unmodified automation is not reloaded."""
    with patch(
        "homeassistant.components.automation.AutomationEntity", wraps=AutomationEntity
    ) as automation_entity_init:
        config = {automation.DOMAIN: [automation_config]}
        assert await async_setup_component(hass, automation.DOMAIN, config)
        assert automation_entity_init.call_count == 1
        automation_entity_init.reset_mock()

        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

        # Reload the automations without any change
        with patch(
            "homeassistant.config.load_yaml_config_file",
            autospec=True,
            return_value=config,
        ):
            await hass.services.async_call(
                automation.DOMAIN, SERVICE_RELOAD, blocking=True
            )

        assert automation_entity_init.call_count == 0
        automation_entity_init.reset_mock()

        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2


@pytest.mark.parametrize("extra_config", ({}, {"id": "sun"}))
async def test_reload_automation_when_blueprint_changes(
    hass: HomeAssistant, calls, extra_config
) -> None:
    """Test an automation is updated at reload if the blueprint has changed."""
    with patch(
        "homeassistant.components.automation.AutomationEntity", wraps=AutomationEntity
    ) as automation_entity_init:
        config = {
            automation.DOMAIN: [
                {
                    "use_blueprint": {
                        "path": "test_event_service.yaml",
                        "input": {
                            "trigger_event": "test_event",
                            "service_to_call": "test.automation",
                            "a_number": 5,
                        },
                    }
                }
            ]
        }
        config[automation.DOMAIN][0].update(**extra_config)
        assert await async_setup_component(hass, automation.DOMAIN, config)
        assert automation_entity_init.call_count == 1
        automation_entity_init.reset_mock()

        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

        # Reload the automations without any change, but with updated blueprint
        blueprint_path = automation.async_get_blueprints(hass).blueprint_folder
        blueprint_config = yaml.load_yaml(blueprint_path / "test_event_service.yaml")
        blueprint_config["action"] = [blueprint_config["action"]]
        blueprint_config["action"].append(blueprint_config["action"][-1])

        with patch(
            "homeassistant.config.load_yaml_config_file",
            autospec=True,
            return_value=config,
        ), patch(
            "homeassistant.components.blueprint.models.yaml.load_yaml",
            autospec=True,
            return_value=blueprint_config,
        ):
            await hass.services.async_call(
                automation.DOMAIN, SERVICE_RELOAD, blocking=True
            )

        assert automation_entity_init.call_count == 1
        automation_entity_init.reset_mock()

        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 3


async def test_automation_restore_state(hass: HomeAssistant) -> None:
    """Ensure states are restored on startup."""
    time = dt_util.utcnow()

    mock_restore_cache(
        hass,
        (
            State("automation.hello", STATE_ON),
            State("automation.bye", STATE_OFF, {"last_triggered": time}),
        ),
    )

    config = {
        automation.DOMAIN: [
            {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event_hello"},
                "action": {"service": "test.automation"},
            },
            {
                "alias": "bye",
                "trigger": {"platform": "event", "event_type": "test_event_bye"},
                "action": {"service": "test.automation"},
            },
        ]
    }

    assert await async_setup_component(hass, automation.DOMAIN, config)

    state = hass.states.get("automation.hello")
    assert state
    assert state.state == STATE_ON
    assert state.attributes["last_triggered"] is None

    state = hass.states.get("automation.bye")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes["last_triggered"] == time

    calls = async_mock_service(hass, "test", "automation")

    assert automation.is_on(hass, "automation.bye") is False

    hass.bus.async_fire("test_event_bye")
    await hass.async_block_till_done()
    assert len(calls) == 0

    assert automation.is_on(hass, "automation.hello")

    hass.bus.async_fire("test_event_hello")
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_initial_value_off(hass: HomeAssistant) -> None:
    """Test initial value off."""
    calls = async_mock_service(hass, "test", "automation")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "initial_state": "off",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )
    assert not automation.is_on(hass, "automation.hello")

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_initial_value_on(hass: HomeAssistant) -> None:
    """Test initial value on."""
    hass.state = CoreState.not_running
    calls = async_mock_service(hass, "test", "automation")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "initial_state": "on",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {
                    "service": "test.automation",
                    "entity_id": ["hello.world", "hello.world2"],
                },
            }
        },
    )
    assert automation.is_on(hass, "automation.hello")

    await hass.async_start()
    await hass.async_block_till_done()
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_initial_value_off_but_restore_on(hass: HomeAssistant) -> None:
    """Test initial value off and restored state is turned on."""
    hass.state = CoreState.not_running
    calls = async_mock_service(hass, "test", "automation")
    mock_restore_cache(hass, (State("automation.hello", STATE_ON),))

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "initial_state": "off",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )
    assert not automation.is_on(hass, "automation.hello")

    await hass.async_start()
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_initial_value_on_but_restore_off(hass: HomeAssistant) -> None:
    """Test initial value on and restored state is turned off."""
    calls = async_mock_service(hass, "test", "automation")
    mock_restore_cache(hass, (State("automation.hello", STATE_OFF),))

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "initial_state": "on",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )
    assert automation.is_on(hass, "automation.hello")

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_no_initial_value_and_restore_off(hass: HomeAssistant) -> None:
    """Test initial value off and restored state is turned on."""
    calls = async_mock_service(hass, "test", "automation")
    mock_restore_cache(hass, (State("automation.hello", STATE_OFF),))

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )
    assert not automation.is_on(hass, "automation.hello")

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_automation_is_on_if_no_initial_state_or_restore(
    hass: HomeAssistant,
) -> None:
    """Test initial value is on when no initial state or restored state."""
    calls = async_mock_service(hass, "test", "automation")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )
    assert automation.is_on(hass, "automation.hello")

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_automation_not_trigger_on_bootstrap(hass: HomeAssistant) -> None:
    """Test if automation is not trigger on bootstrap."""
    hass.state = CoreState.not_running
    calls = async_mock_service(hass, "test", "automation")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )
    assert automation.is_on(hass, "automation.hello")

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert automation.is_on(hass, "automation.hello")

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert ["hello.world"] == calls[0].data.get(ATTR_ENTITY_ID)


@pytest.mark.parametrize(
    ("broken_config", "problem", "details"),
    (
        (
            {},
            "could not be validated",
            "required key not provided @ data['action']",
        ),
        (
            {
                "trigger": {"platform": "automation"},
                "action": [],
            },
            "failed to setup triggers",
            "Integration 'automation' does not provide trigger support.",
        ),
        (
            {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "state",
                    # The UUID will fail being resolved to en entity_id
                    "entity_id": "abcdabcdabcdabcdabcdabcdabcdabcd",
                    "state": "blah",
                },
                "action": [],
            },
            "failed to setup conditions",
            "Unknown entity registry entry abcdabcdabcdabcdabcdabcdabcdabcd.",
        ),
        (
            {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {
                    "condition": "state",
                    # The UUID will fail being resolved to en entity_id
                    "entity_id": "abcdabcdabcdabcdabcdabcdabcdabcd",
                    "state": "blah",
                },
            },
            "failed to setup actions",
            "Unknown entity registry entry abcdabcdabcdabcdabcdabcdabcdabcd.",
        ),
    ),
)
async def test_automation_bad_config_validation(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    broken_config,
    problem,
    details,
) -> None:
    """Test bad automation configuration which can be detected during validation."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {"alias": "bad_automation", **broken_config},
                {
                    "alias": "good_automation",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": {
                        "service": "test.automation",
                        "entity_id": "hello.world",
                    },
                },
            ]
        },
    )

    # Check we get the expected error message
    assert (
        f"Automation with alias 'bad_automation' {problem} and has been disabled:"
        f" {details}"
    ) in caplog.text

    # Make sure both automations are setup
    assert set(hass.states.async_entity_ids("automation")) == {
        "automation.bad_automation",
        "automation.good_automation",
    }
    # The automation failing validation should be unavailable
    assert hass.states.get("automation.bad_automation").state == STATE_UNAVAILABLE


async def test_automation_with_error_in_script(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test automation with an error in script."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert "Service not found" in caplog.text
    assert "Traceback" not in caplog.text

    issues = await get_repairs(hass, hass_ws_client)
    assert len(issues) == 1
    assert issues[0]["issue_id"] == "automation.hello_service_not_found_test.automation"


async def test_automation_with_error_in_script_2(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test automation with an error in script."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": None, "entity_id": "hello.world"},
            }
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert "string value is None" in caplog.text


async def test_automation_restore_last_triggered_with_initial_state(
    hass: HomeAssistant,
) -> None:
    """Ensure last_triggered is restored, even when initial state is set."""
    time = dt_util.utcnow()

    mock_restore_cache(
        hass,
        (
            State("automation.hello", STATE_ON),
            State("automation.bye", STATE_ON, {"last_triggered": time}),
            State("automation.solong", STATE_OFF, {"last_triggered": time}),
        ),
    )

    config = {
        automation.DOMAIN: [
            {
                "alias": "hello",
                "initial_state": "off",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation"},
            },
            {
                "alias": "bye",
                "initial_state": "off",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation"},
            },
            {
                "alias": "solong",
                "initial_state": "on",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation"},
            },
        ]
    }

    await async_setup_component(hass, automation.DOMAIN, config)

    state = hass.states.get("automation.hello")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes["last_triggered"] is None

    state = hass.states.get("automation.bye")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes["last_triggered"] == time

    state = hass.states.get("automation.solong")
    assert state
    assert state.state == STATE_ON
    assert state.attributes["last_triggered"] == time


async def test_extraction_functions_not_setup(hass: HomeAssistant) -> None:
    """Test extraction functions when automation is not setup."""
    assert automation.automations_with_area(hass, "area-in-both") == []
    assert automation.areas_in_automation(hass, "automation.test") == []
    assert automation.automations_with_blueprint(hass, "blabla.yaml") == []
    assert automation.blueprint_in_automation(hass, "automation.test") is None
    assert automation.automations_with_device(hass, "device-in-both") == []
    assert automation.devices_in_automation(hass, "automation.test") == []
    assert automation.automations_with_entity(hass, "light.in_both") == []
    assert automation.entities_in_automation(hass, "automation.test") == []


async def test_extraction_functions_unknown_automation(hass: HomeAssistant) -> None:
    """Test extraction functions for an unknown automation."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert automation.areas_in_automation(hass, "automation.unknown") == []
    assert automation.blueprint_in_automation(hass, "automation.unknown") is None
    assert automation.devices_in_automation(hass, "automation.unknown") == []
    assert automation.entities_in_automation(hass, "automation.unknown") == []


async def test_extraction_functions_unavailable_automation(hass: HomeAssistant) -> None:
    """Test extraction functions for an unknown automation."""
    entity_id = "automation.test1"
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "alias": "test1",
                }
            ]
        },
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert automation.automations_with_area(hass, "area-in-both") == []
    assert automation.areas_in_automation(hass, entity_id) == []
    assert automation.automations_with_blueprint(hass, "blabla.yaml") == []
    assert automation.blueprint_in_automation(hass, entity_id) is None
    assert automation.automations_with_device(hass, "device-in-both") == []
    assert automation.devices_in_automation(hass, entity_id) == []
    assert automation.automations_with_entity(hass, "light.in_both") == []
    assert automation.entities_in_automation(hass, entity_id) == []


async def test_extraction_functions(hass: HomeAssistant) -> None:
    """Test extraction functions."""
    await async_setup_component(hass, "homeassistant", {})
    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "alias": "test1",
                    "trigger": [
                        {"platform": "state", "entity_id": "sensor.trigger_state"},
                        {
                            "platform": "numeric_state",
                            "entity_id": "sensor.trigger_numeric_state",
                            "above": 10,
                        },
                        {
                            "platform": "calendar",
                            "entity_id": "calendar.trigger_calendar",
                            "event": "start",
                        },
                        {
                            "platform": "event",
                            "event_type": "state_changed",
                            "event_data": {"entity_id": "sensor.trigger_event"},
                        },
                        # entity_id is a list of strings (not supported)
                        {
                            "platform": "event",
                            "event_type": "state_changed",
                            "event_data": {"entity_id": ["sensor.trigger_event2"]},
                        },
                        # entity_id is not a valid entity ID
                        {
                            "platform": "event",
                            "event_type": "state_changed",
                            "event_data": {"entity_id": "abc"},
                        },
                        # entity_id is not a string
                        {
                            "platform": "event",
                            "event_type": "state_changed",
                            "event_data": {"entity_id": 123},
                        },
                    ],
                    "condition": {
                        "condition": "state",
                        "entity_id": "light.condition_state",
                        "state": "on",
                    },
                    "action": [
                        {
                            "service": "test.script",
                            "data": {"entity_id": "light.in_both"},
                        },
                        {
                            "service": "test.script",
                            "data": {"entity_id": "light.in_first"},
                        },
                        {
                            "domain": "light",
                            "device_id": "device-in-both",
                            "entity_id": "light.bla",
                            "type": "turn_on",
                        },
                        {
                            "service": "test.test",
                            "target": {"area_id": "area-in-both"},
                        },
                    ],
                },
                {
                    "alias": "test2",
                    "trigger": [
                        {
                            "platform": "device",
                            "domain": "light",
                            "type": "turned_on",
                            "entity_id": "light.trigger_2",
                            "device_id": "trigger-device-2",
                        },
                        {
                            "platform": "tag",
                            "tag_id": "1234",
                            "device_id": "device-trigger-tag1",
                        },
                        {
                            "platform": "tag",
                            "tag_id": "1234",
                            "device_id": ["device-trigger-tag2", "device-trigger-tag3"],
                        },
                        {
                            "platform": "event",
                            "event_type": "esphome.button_pressed",
                            "event_data": {"device_id": "device-trigger-event"},
                        },
                        # device_id is a list of strings (not supported)
                        {
                            "platform": "event",
                            "event_type": "esphome.button_pressed",
                            "event_data": {"device_id": ["device-trigger-event2"]},
                        },
                        # device_id is not a string
                        {
                            "platform": "event",
                            "event_type": "esphome.button_pressed",
                            "event_data": {"device_id": 123},
                        },
                    ],
                    "condition": {
                        "condition": "device",
                        "device_id": "condition-device",
                        "domain": "light",
                        "type": "is_on",
                        "entity_id": "light.bla",
                    },
                    "action": [
                        {
                            "service": "test.script",
                            "data": {"entity_id": "light.in_both"},
                        },
                        {
                            "condition": "state",
                            "entity_id": "sensor.condition",
                            "state": "100",
                        },
                        {"scene": "scene.hello"},
                        {
                            "domain": "light",
                            "device_id": "device-in-both",
                            "entity_id": "light.bla",
                            "type": "turn_on",
                        },
                        {
                            "domain": "light",
                            "device_id": "device-in-last",
                            "entity_id": "light.bla",
                            "type": "turn_on",
                        },
                    ],
                },
                {
                    "alias": "test3",
                    "trigger": [
                        {
                            "platform": "event",
                            "event_type": "esphome.button_pressed",
                            "event_data": {"area_id": "area-trigger-event"},
                        },
                        # area_id is a list of strings (not supported)
                        {
                            "platform": "event",
                            "event_type": "esphome.button_pressed",
                            "event_data": {"area_id": ["area-trigger-event2"]},
                        },
                        # area_id is not a string
                        {
                            "platform": "event",
                            "event_type": "esphome.button_pressed",
                            "event_data": {"area_id": 123},
                        },
                    ],
                    "condition": {
                        "condition": "device",
                        "device_id": "condition-device",
                        "domain": "light",
                        "type": "is_on",
                        "entity_id": "light.bla",
                    },
                    "action": [
                        {
                            "service": "test.script",
                            "data": {"entity_id": "light.in_both"},
                        },
                        {
                            "condition": "state",
                            "entity_id": "sensor.condition",
                            "state": "100",
                        },
                        {"scene": "scene.hello"},
                        {
                            "service": "test.test",
                            "target": {"area_id": "area-in-both"},
                        },
                        {
                            "service": "test.test",
                            "target": {"area_id": "area-in-last"},
                        },
                    ],
                },
            ]
        },
    )

    assert set(automation.automations_with_entity(hass, "light.in_both")) == {
        "automation.test1",
        "automation.test2",
        "automation.test3",
    }
    assert set(automation.entities_in_automation(hass, "automation.test1")) == {
        "calendar.trigger_calendar",
        "sensor.trigger_state",
        "sensor.trigger_numeric_state",
        "sensor.trigger_event",
        "light.condition_state",
        "light.in_both",
        "light.in_first",
    }
    assert set(automation.automations_with_device(hass, "device-in-both")) == {
        "automation.test1",
        "automation.test2",
    }
    assert set(automation.devices_in_automation(hass, "automation.test2")) == {
        "trigger-device-2",
        "condition-device",
        "device-in-both",
        "device-in-last",
        "device-trigger-event",
        "device-trigger-tag1",
        "device-trigger-tag2",
        "device-trigger-tag3",
    }
    assert set(automation.automations_with_area(hass, "area-in-both")) == {
        "automation.test1",
        "automation.test3",
    }
    assert set(automation.areas_in_automation(hass, "automation.test3")) == {
        "area-in-both",
        "area-in-last",
    }
    assert automation.blueprint_in_automation(hass, "automation.test3") is None


async def test_logbook_humanify_automation_triggered_event(hass: HomeAssistant) -> None:
    """Test humanifying Automation Trigger event."""
    hass.config.components.add("recorder")
    await async_setup_component(hass, automation.DOMAIN, {})
    await async_setup_component(hass, "logbook", {})

    event1, event2 = mock_humanify(
        hass,
        [
            MockRow(
                EVENT_AUTOMATION_TRIGGERED,
                {ATTR_ENTITY_ID: "automation.hello", ATTR_NAME: "Hello Automation"},
            ),
            MockRow(
                EVENT_AUTOMATION_TRIGGERED,
                {
                    ATTR_ENTITY_ID: "automation.bye",
                    ATTR_NAME: "Bye Automation",
                    ATTR_SOURCE: "source of trigger",
                },
            ),
        ],
    )

    assert event1["name"] == "Hello Automation"
    assert event1["domain"] == "automation"
    assert event1["message"] == "triggered"
    assert event1["entity_id"] == "automation.hello"

    assert event2["name"] == "Bye Automation"
    assert event2["domain"] == "automation"
    assert event2["message"] == "triggered by source of trigger"
    assert event2["entity_id"] == "automation.bye"


async def test_automation_variables(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test automation variables."""
    calls = async_mock_service(hass, "test", "automation")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "variables": {
                        "test_var": "defined_in_config",
                        "event_type": "{{ trigger.event.event_type }}",
                        "this_variables": "{{this.entity_id}}",
                    },
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": {
                        "service": "test.automation",
                        "data": {
                            "value": "{{ test_var }}",
                            "event_type": "{{ event_type }}",
                            "this_template": "{{this.entity_id}}",
                            "this_variables": "{{this_variables}}",
                        },
                    },
                },
                {
                    "variables": {
                        "test_var": "defined_in_config",
                    },
                    "trigger": {"platform": "event", "event_type": "test_event_2"},
                    "condition": {
                        "condition": "template",
                        "value_template": "{{ trigger.event.data.pass_condition }}",
                    },
                    "action": {
                        "service": "test.automation",
                    },
                },
                {
                    "variables": {
                        "test_var": "{{ trigger.event.data.break + 1 }}",
                    },
                    "trigger": {"platform": "event", "event_type": "test_event_3"},
                    "action": {
                        "service": "test.automation",
                    },
                },
            ]
        },
    )
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["value"] == "defined_in_config"
    assert calls[0].data["event_type"] == "test_event"
    # Verify this available to all templates
    assert calls[0].data.get("this_template") == "automation.automation_0"
    # Verify this available during variables rendering
    assert calls[0].data.get("this_variables") == "automation.automation_0"
    assert "Error rendering variables" not in caplog.text

    hass.bus.async_fire("test_event_2")
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.bus.async_fire("test_event_2", {"pass_condition": True})
    await hass.async_block_till_done()
    assert len(calls) == 2

    assert "Error rendering variables" not in caplog.text
    hass.bus.async_fire("test_event_3")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert "Error rendering variables" in caplog.text

    hass.bus.async_fire("test_event_3", {"break": 0})
    await hass.async_block_till_done()
    assert len(calls) == 3


async def test_automation_trigger_variables(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test automation trigger variables."""
    calls = async_mock_service(hass, "test", "automation")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "variables": {
                        "event_type": "{{ trigger.event.event_type }}",
                    },
                    "trigger_variables": {
                        "test_var": "defined_in_config",
                    },
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": {
                        "service": "test.automation",
                        "data": {
                            "value": "{{ test_var }}",
                            "event_type": "{{ event_type }}",
                        },
                    },
                },
                {
                    "variables": {
                        "event_type": "{{ trigger.event.event_type }}",
                        "test_var": "overridden_in_config",
                    },
                    "trigger_variables": {
                        "test_var": "defined_in_config",
                        "this_trigger_variables": "{{this.entity_id}}",
                    },
                    "trigger": {"platform": "event", "event_type": "test_event_2"},
                    "action": {
                        "service": "test.automation",
                        "data": {
                            "value": "{{ test_var }}",
                            "event_type": "{{ event_type }}",
                            "this_template": "{{this.entity_id}}",
                            "this_trigger_variables": "{{this_trigger_variables}}",
                        },
                    },
                },
            ]
        },
    )
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["value"] == "defined_in_config"
    assert calls[0].data["event_type"] == "test_event"

    hass.bus.async_fire("test_event_2")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["value"] == "overridden_in_config"
    assert calls[1].data["event_type"] == "test_event_2"
    # Verify this available to all templates
    assert calls[1].data.get("this_template") == "automation.automation_1"
    # Verify this available during trigger variables rendering
    assert calls[1].data.get("this_trigger_variables") == "automation.automation_1"
    assert "Error rendering variables" not in caplog.text


async def test_automation_bad_trigger_variables(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test automation trigger variables accessing hass is rejected."""
    calls = async_mock_service(hass, "test", "automation")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger_variables": {
                        "test_var": "{{ states('foo.bar') }}",
                    },
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": {
                        "service": "test.automation",
                    },
                },
            ]
        },
    )
    hass.bus.async_fire("test_event")
    assert "Use of 'states' is not supported in limited templates" in caplog.text

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_automation_this_var_always(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test automation always has reference to this, even with no variable or trigger variables configured."""
    calls = async_mock_service(hass, "test", "automation")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": {
                        "service": "test.automation",
                        "data": {
                            "this_template": "{{this.entity_id}}",
                        },
                    },
                },
            ]
        },
    )
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1
    # Verify this available to all templates
    assert calls[0].data.get("this_template") == "automation.automation_0"
    assert "Error rendering variables" not in caplog.text


async def test_blueprint_automation(hass: HomeAssistant, calls) -> None:
    """Test blueprint automation."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": "test_event_service.yaml",
                    "input": {
                        "trigger_event": "blueprint_event",
                        "service_to_call": "test.automation",
                        "a_number": 5,
                    },
                }
            }
        },
    )
    hass.bus.async_fire("blueprint_event")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert automation.entities_in_automation(hass, "automation.automation_0") == [
        "light.kitchen"
    ]
    assert (
        automation.blueprint_in_automation(hass, "automation.automation_0")
        == "test_event_service.yaml"
    )
    assert automation.automations_with_blueprint(hass, "test_event_service.yaml") == [
        "automation.automation_0"
    ]


@pytest.mark.parametrize(
    ("blueprint_inputs", "problem", "details"),
    (
        (
            # No input
            {},
            "Failed to generate automation from blueprint",
            "Missing input a_number, service_to_call, trigger_event",
        ),
        (
            # Missing input
            {"trigger_event": "blueprint_event", "a_number": 5},
            "Failed to generate automation from blueprint",
            "Missing input service_to_call",
        ),
        (
            # Wrong input
            {
                "trigger_event": "blueprint_event",
                "service_to_call": {"dict": "not allowed"},
                "a_number": 5,
            },
            "Blueprint 'Call service based on event' generated invalid automation",
            (
                "value should be a string for dictionary value @"
                " data['action'][0]['service']"
            ),
        ),
    ),
)
async def test_blueprint_automation_bad_config(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    blueprint_inputs,
    problem,
    details,
) -> None:
    """Test blueprint automation with bad inputs."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": "test_event_service.yaml",
                    "input": blueprint_inputs,
                }
            }
        },
    )
    assert problem in caplog.text
    assert details in caplog.text


async def test_blueprint_automation_fails_substitution(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test blueprint automation with bad inputs."""
    with patch(
        "homeassistant.components.blueprint.models.BlueprintInputs.async_substitute",
        side_effect=yaml.UndefinedSubstitution("blah"),
    ):
        assert await async_setup_component(
            hass,
            "automation",
            {
                "automation": {
                    "use_blueprint": {
                        "path": "test_event_service.yaml",
                        "input": {
                            "trigger_event": "test_event",
                            "service_to_call": "test.automation",
                            "a_number": 5,
                        },
                    }
                }
            },
        )
    assert (
        "Blueprint 'Call service based on event' failed to generate automation with"
        " inputs {'trigger_event': 'test_event', 'service_to_call': 'test.automation',"
        " 'a_number': 5}: No substitution found for input blah"
    ) in caplog.text


async def test_trigger_service(hass: HomeAssistant, calls) -> None:
    """Test the automation trigger service."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {
                    "service": "test.automation",
                    "data_template": {"trigger": "{{ trigger }}"},
                },
            }
        },
    )
    context = Context()
    await hass.services.async_call(
        "automation",
        "trigger",
        {"entity_id": "automation.hello"},
        blocking=True,
        context=context,
    )

    assert len(calls) == 1
    assert calls[0].data.get("trigger") == {"platform": None}
    assert calls[0].context.parent_id is context.id


async def test_trigger_condition_implicit_id(hass: HomeAssistant, calls) -> None:
    """Test triggers."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": [
                    {"platform": "event", "event_type": "test_event1"},
                    {"platform": "event", "event_type": "test_event2"},
                    {"platform": "event", "event_type": "test_event3"},
                ],
                "action": {
                    "choose": [
                        {
                            "conditions": {"condition": "trigger", "id": [0, "2"]},
                            "sequence": {
                                "service": "test.automation",
                                "data": {"param": "one"},
                            },
                        },
                        {
                            "conditions": {"condition": "trigger", "id": "1"},
                            "sequence": {
                                "service": "test.automation",
                                "data": {"param": "two"},
                            },
                        },
                    ]
                },
            }
        },
    )

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[-1].data.get("param") == "one"

    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[-1].data.get("param") == "two"

    hass.bus.async_fire("test_event3")
    await hass.async_block_till_done()
    assert len(calls) == 3
    assert calls[-1].data.get("param") == "one"


async def test_trigger_condition_explicit_id(hass: HomeAssistant, calls) -> None:
    """Test triggers."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": [
                    {"platform": "event", "event_type": "test_event1", "id": "one"},
                    {"platform": "event", "event_type": "test_event2", "id": "two"},
                ],
                "action": {
                    "choose": [
                        {
                            "conditions": {"condition": "trigger", "id": "one"},
                            "sequence": {
                                "service": "test.automation",
                                "data": {"param": "one"},
                            },
                        },
                        {
                            "conditions": {"condition": "trigger", "id": "two"},
                            "sequence": {
                                "service": "test.automation",
                                "data": {"param": "two"},
                            },
                        },
                    ]
                },
            }
        },
    )

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[-1].data.get("param") == "one"

    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[-1].data.get("param") == "two"


@pytest.mark.parametrize(
    ("automation_mode", "automation_runs"),
    (
        (SCRIPT_MODE_PARALLEL, 2),
        (SCRIPT_MODE_QUEUED, 2),
        (SCRIPT_MODE_RESTART, 2),
        (SCRIPT_MODE_SINGLE, 1),
    ),
)
@pytest.mark.parametrize(
    ("script_mode", "script_warning_msg"),
    (
        (SCRIPT_MODE_PARALLEL, "script1: Maximum number of runs exceeded"),
        (SCRIPT_MODE_QUEUED, "script1: Disallowed recursion detected"),
        (SCRIPT_MODE_RESTART, "script1: Disallowed recursion detected"),
        (SCRIPT_MODE_SINGLE, "script1: Already running"),
    ),
)
@pytest.mark.parametrize("wait_for_stop_scripts_after_shutdown", [True])
async def test_recursive_automation_starting_script(
    hass: HomeAssistant,
    automation_mode,
    automation_runs,
    script_mode,
    script_warning_msg,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test starting automations does not interfere with script deadlock prevention."""

    # Fail if additional script modes are added to
    # make sure we cover all script modes in tests
    assert [
        SCRIPT_MODE_PARALLEL,
        SCRIPT_MODE_QUEUED,
        SCRIPT_MODE_RESTART,
        SCRIPT_MODE_SINGLE,
    ] == SCRIPT_MODE_CHOICES

    stop_scripts_at_shutdown_called = asyncio.Event()
    real_stop_scripts_at_shutdown = _async_stop_scripts_at_shutdown

    async def mock_stop_scripts_at_shutdown(*args):
        await real_stop_scripts_at_shutdown(*args)
        stop_scripts_at_shutdown_called.set()

    with patch(
        "homeassistant.helpers.script._async_stop_scripts_at_shutdown",
        wraps=mock_stop_scripts_at_shutdown,
    ):
        assert await async_setup_component(
            hass,
            "script",
            {
                "script": {
                    "script1": {
                        "mode": script_mode,
                        "sequence": [
                            {"event": "trigger_automation"},
                            {
                                "wait_template": (
                                    "{{ float(states('sensor.test'), 0) >="
                                    f" {automation_runs} }}}}"
                                )
                            },
                            {"service": "script.script1"},
                            {"service": "test.script_done"},
                        ],
                    },
                }
            },
        )

        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "mode": automation_mode,
                    "trigger": [
                        {"platform": "event", "event_type": "trigger_automation"},
                    ],
                    "action": [
                        {"service": "test.automation_started"},
                        {"service": "script.script1"},
                    ],
                }
            },
        )

        script_done_event = asyncio.Event()
        script_done = []
        automation_started = []
        automation_triggered = []

        async def async_service_handler(service: ServiceCall):
            if service.service == "automation_started":
                automation_started.append(service)
            elif service.service == "script_done":
                script_done.append(service)
                if len(script_done) == 1:
                    script_done_event.set()

        async def async_automation_triggered(event):
            """Listen to automation_triggered event from the automation integration."""
            automation_triggered.append(event)
            hass.states.async_set("sensor.test", str(len(automation_triggered)))

        hass.services.async_register("test", "script_done", async_service_handler)
        hass.services.async_register(
            "test", "automation_started", async_service_handler
        )
        hass.bus.async_listen("automation_triggered", async_automation_triggered)

        hass.bus.async_fire("trigger_automation")
        await asyncio.wait_for(script_done_event.wait(), 10)

        # Trigger 1st stage script shutdown
        hass.state = CoreState.stopping
        hass.bus.async_fire("homeassistant_stop")
        await asyncio.wait_for(stop_scripts_at_shutdown_called.wait(), 10)

        # Trigger 2nd stage script shutdown
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
        await hass.async_block_till_done()

        assert script_warning_msg in caplog.text


@pytest.mark.parametrize("automation_mode", SCRIPT_MODE_CHOICES)
@pytest.mark.parametrize("wait_for_stop_scripts_after_shutdown", [True])
async def test_recursive_automation(
    hass: HomeAssistant, automation_mode, caplog: pytest.LogCaptureFixture
) -> None:
    """Test automation triggering itself.

    - Illegal recursion detection should not be triggered
    - Home Assistant should not hang on shut down
    """
    stop_scripts_at_shutdown_called = asyncio.Event()
    real_stop_scripts_at_shutdown = _async_stop_scripts_at_shutdown

    async def stop_scripts_at_shutdown(*args):
        await real_stop_scripts_at_shutdown(*args)
        stop_scripts_at_shutdown_called.set()

    with patch(
        "homeassistant.helpers.script._async_stop_scripts_at_shutdown",
        wraps=stop_scripts_at_shutdown,
    ):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "mode": automation_mode,
                    "trigger": [
                        {"platform": "event", "event_type": "trigger_automation"},
                    ],
                    "action": [
                        {"event": "trigger_automation"},
                        {"service": "test.automation_done"},
                    ],
                }
            },
        )

        service_called = asyncio.Event()

        async def async_service_handler(service):
            if service.service == "automation_done":
                service_called.set()

        hass.services.async_register("test", "automation_done", async_service_handler)

        hass.bus.async_fire("trigger_automation")
        await asyncio.wait_for(service_called.wait(), 1)

        # Trigger 1st stage script shutdown
        hass.state = CoreState.stopping
        hass.bus.async_fire("homeassistant_stop")
        await asyncio.wait_for(stop_scripts_at_shutdown_called.wait(), 1)

        # Trigger 2nd stage script shutdown
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=90))
        await hass.async_block_till_done()

        assert "Disallowed recursion detected" not in caplog.text


async def test_websocket_config(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test config command."""
    config = {
        "alias": "hello",
        "trigger": {"platform": "event", "event_type": "test_event"},
        "action": {"service": "test.automation", "data": 100},
    }
    assert await async_setup_component(
        hass, automation.DOMAIN, {automation.DOMAIN: config}
    )
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "automation/config",
            "entity_id": "automation.hello",
        }
    )

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"config": config}

    await client.send_json(
        {
            "id": 6,
            "type": "automation/config",
            "entity_id": "automation.not_exist",
        }
    )

    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"
