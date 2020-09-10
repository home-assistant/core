"""The tests for the automation component."""
import asyncio

import pytest

from homeassistant.components import logbook
import homeassistant.components.automation as automation
from homeassistant.components.automation import (
    ATTR_SOURCE,
    DOMAIN,
    EVENT_AUTOMATION_RELOADED,
    EVENT_AUTOMATION_TRIGGERED,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
    EVENT_HOMEASSISTANT_STARTED,
    SERVICE_TURN_OFF,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, CoreState, State, callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import Mock, patch
from tests.common import assert_setup_component, async_mock_service, mock_restore_cache
from tests.components.automation import common
from tests.components.logbook.test_init import MockLazyEventPartialState


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_service_data_not_a_dict(hass, calls):
    """Test service data not dict."""
    with assert_setup_component(0, automation.DOMAIN):
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


async def test_service_specify_data(hass, calls):
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
                        "some": "{{ trigger.platform }} - "
                        "{{ trigger.event.event_type }}"
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


async def test_service_specify_entity_id(hass, calls):
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


async def test_service_specify_entity_id_list(hass, calls):
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


async def test_two_triggers(hass, calls):
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


async def test_trigger_service_ignoring_condition(hass, calls):
    """Test triggers."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "test",
                "trigger": [{"platform": "event", "event_type": "test_event"}],
                "condition": {
                    "condition": "state",
                    "entity_id": "non.existing",
                    "state": "beer",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 0

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


async def test_two_conditions_with_and(hass, calls):
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


async def test_shorthand_conditions_template(hass, calls):
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


async def test_automation_list_setting(hass, calls):
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


async def test_automation_calling_two_actions(hass, calls):
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


async def test_shared_context(hass, calls):
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


async def test_services(hass, calls):
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

    await common.async_turn_off(hass, entity_id)
    await hass.async_block_till_done()

    assert not automation.is_on(hass, entity_id)
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1

    await common.async_toggle(hass, entity_id)
    await hass.async_block_till_done()

    assert automation.is_on(hass, entity_id)
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 2

    await common.async_toggle(hass, entity_id)
    await hass.async_block_till_done()

    assert not automation.is_on(hass, entity_id)
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 2

    await common.async_toggle(hass, entity_id)
    await hass.async_block_till_done()

    await common.async_trigger(hass, entity_id)
    await hass.async_block_till_done()
    assert len(calls) == 3

    await common.async_turn_off(hass, entity_id)
    await hass.async_block_till_done()
    await common.async_trigger(hass, entity_id)
    await hass.async_block_till_done()
    assert len(calls) == 4

    await common.async_turn_on(hass, entity_id)
    await hass.async_block_till_done()
    assert automation.is_on(hass, entity_id)


async def test_reload_config_service(hass, calls, hass_admin_user, hass_read_only_user):
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

    test_reload_event = []
    hass.bus.async_listen(
        EVENT_AUTOMATION_RELOADED, lambda event: test_reload_event.append(event)
    )

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
            await common.async_reload(hass, Context(user_id=hass_read_only_user.id))
            await hass.async_block_till_done()
        await common.async_reload(hass, Context(user_id=hass_admin_user.id))
        await hass.async_block_till_done()
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


async def test_reload_config_when_invalid_config(hass, calls):
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
        await common.async_reload(hass)
        await hass.async_block_till_done()

    assert hass.states.get("automation.hello") is None

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_reload_config_handles_load_fails(hass, calls):
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
        await common.async_reload(hass)
        await hass.async_block_till_done()

    assert hass.states.get("automation.hello") is not None

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 2


@pytest.mark.parametrize("service", ["turn_off_stop", "turn_off_no_stop", "reload"])
async def test_automation_stops(hass, calls, service):
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
        with patch(
            "homeassistant.config.load_yaml_config_file",
            autospec=True,
            return_value=config,
        ):
            await common.async_reload(hass)

    hass.states.async_set(test_entity, "goodbye")
    await hass.async_block_till_done()

    assert len(calls) == (1 if service == "turn_off_no_stop" else 0)


async def test_automation_restore_state(hass):
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


async def test_initial_value_off(hass):
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


async def test_initial_value_on(hass):
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


async def test_initial_value_off_but_restore_on(hass):
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


async def test_initial_value_on_but_restore_off(hass):
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


async def test_no_initial_value_and_restore_off(hass):
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


async def test_automation_is_on_if_no_initial_state_or_restore(hass):
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


async def test_automation_not_trigger_on_bootstrap(hass):
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


async def test_automation_bad_trigger(hass, caplog):
    """Test bad trigger configuration."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "automation"},
                "action": [],
            }
        },
    )
    assert "Integration 'automation' does not provide trigger support." in caplog.text


async def test_automation_with_error_in_script(hass, caplog):
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


async def test_automation_with_error_in_script_2(hass, caplog):
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


async def test_automation_restore_last_triggered_with_initial_state(hass):
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


async def test_extraction_functions(hass):
    """Test extraction functions."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "alias": "test1",
                    "trigger": {"platform": "state", "entity_id": "sensor.trigger_1"},
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
                    ],
                },
                {
                    "alias": "test2",
                    "trigger": {
                        "platform": "device",
                        "domain": "light",
                        "type": "turned_on",
                        "entity_id": "light.trigger_2",
                        "device_id": "trigger-device-2",
                    },
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
            ]
        },
    )

    assert set(automation.automations_with_entity(hass, "light.in_both")) == {
        "automation.test1",
        "automation.test2",
    }
    assert set(automation.entities_in_automation(hass, "automation.test1")) == {
        "sensor.trigger_1",
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
    }


async def test_logbook_humanify_automation_triggered_event(hass):
    """Test humanifying Automation Trigger event."""
    hass.config.components.add("recorder")
    await async_setup_component(hass, automation.DOMAIN, {})
    await async_setup_component(hass, "logbook", {})
    entity_attr_cache = logbook.EntityAttributeCache(hass)

    event1, event2 = list(
        logbook.humanify(
            hass,
            [
                MockLazyEventPartialState(
                    EVENT_AUTOMATION_TRIGGERED,
                    {ATTR_ENTITY_ID: "automation.hello", ATTR_NAME: "Hello Automation"},
                ),
                MockLazyEventPartialState(
                    EVENT_AUTOMATION_TRIGGERED,
                    {
                        ATTR_ENTITY_ID: "automation.bye",
                        ATTR_NAME: "Bye Automation",
                        ATTR_SOURCE: "source of trigger",
                    },
                ),
            ],
            entity_attr_cache,
            {},
        )
    )

    assert event1["name"] == "Hello Automation"
    assert event1["domain"] == "automation"
    assert event1["message"] == "has been triggered"
    assert event1["entity_id"] == "automation.hello"

    assert event2["name"] == "Bye Automation"
    assert event2["domain"] == "automation"
    assert event2["message"] == "has been triggered by source of trigger"
    assert event2["entity_id"] == "automation.bye"


async def test_automation_variables(hass):
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
    assert len(calls) == 1

    hass.bus.async_fire("test_event_2", {"pass_condition": True})
    await hass.async_block_till_done()
    assert len(calls) == 2
