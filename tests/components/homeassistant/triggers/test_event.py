"""The tests for the Event automation."""
import pytest

import homeassistant.components.automation as automation
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, SERVICE_TURN_OFF
from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service, mock_component


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture
def context_with_user():
    """Create a context with default user_id."""
    return Context(user_id="test_user_id")


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, "group")


async def test_if_fires_on_event(hass: HomeAssistant, calls) -> None:
    """Test the firing of events."""
    context = Context()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {
                    "service": "test.automation",
                    "data_template": {"id": "{{ trigger.id}}"},
                },
            }
        },
    )

    hass.bus.async_fire("test_event", context=context)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].context.parent_id == context.id

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["id"] == 0


async def test_if_fires_on_templated_event(hass: HomeAssistant, calls) -> None:
    """Test the firing of events."""
    context = Context()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger_variables": {"event_type": "test_event"},
                "trigger": {"platform": "event", "event_type": "{{event_type}}"},
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event", context=context)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].context.parent_id == context.id

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_multiple_events(hass: HomeAssistant, calls) -> None:
    """Test the firing of events."""
    context = Context()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": ["test_event", "test2_event"],
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event", context=context)
    await hass.async_block_till_done()
    hass.bus.async_fire("test2_event", context=context)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[0].context.parent_id == context.id
    assert calls[1].context.parent_id == context.id


async def test_if_fires_on_event_extra_data(
    hass: HomeAssistant, calls, context_with_user
) -> None:
    """Test the firing of events still matches with event data and context."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation"},
            }
        },
    )
    hass.bus.async_fire(
        "test_event", {"extra_key": "extra_data"}, context=context_with_user
    )
    await hass.async_block_till_done()
    assert len(calls) == 1

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_event_with_data_and_context(
    hass: HomeAssistant, calls, context_with_user
) -> None:
    """Test the firing of events with data and context."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {
                        "some_attr": "some_value",
                        "second_attr": "second_value",
                    },
                    "context": {"user_id": context_with_user.user_id},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire(
        "test_event",
        {"some_attr": "some_value", "another": "value", "second_attr": "second_value"},
        context=context_with_user,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.bus.async_fire(
        "test_event",
        {"some_attr": "some_value", "another": "value"},
        context=context_with_user,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1  # No new call

    hass.bus.async_fire(
        "test_event",
        {"some_attr": "some_value", "another": "value", "second_attr": "second_value"},
    )
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_event_with_templated_data_and_context(
    hass: HomeAssistant, calls, context_with_user
) -> None:
    """Test the firing of events with templated data and context."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger_variables": {
                    "attr_1_val": "milk",
                    "attr_2_val": "beer",
                    "user_id": context_with_user.user_id,
                },
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {
                        "attr_1": "{{attr_1_val}}",
                        "attr_2": "{{attr_2_val}}",
                    },
                    "context": {"user_id": "{{user_id}}"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire(
        "test_event",
        {"attr_1": "milk", "another": "value", "attr_2": "beer"},
        context=context_with_user,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.bus.async_fire(
        "test_event",
        {"attr_1": "milk", "another": "value"},
        context=context_with_user,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1  # No new call

    hass.bus.async_fire(
        "test_event",
        {"attr_1": "milk", "another": "value", "attr_2": "beer"},
    )
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_event_with_empty_data_and_context_config(
    hass: HomeAssistant, calls, context_with_user
) -> None:
    """Test the firing of events with empty data and context config.

    The frontend automation editor can produce configurations with an
    empty dict for event_data instead of no key.
    """
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {},
                    "context": {},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire(
        "test_event",
        {"some_attr": "some_value", "another": "value"},
        context=context_with_user,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_event_with_nested_data(hass: HomeAssistant, calls) -> None:
    """Test the firing of events with nested data.

    This test exercises the slow path of using vol.Schema to validate
    matching event data.
    """
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {"parent_attr": {"some_attr": "some_value"}},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire(
        "test_event", {"parent_attr": {"some_attr": "some_value", "another": "value"}}
    )
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_event_with_empty_data(hass: HomeAssistant, calls) -> None:
    """Test the firing of events with empty data.

    This test exercises the fast path to validate matching event data.
    """
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {},
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    hass.bus.async_fire("test_event", {"any_attr": {}})
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_sample_zha_event(hass: HomeAssistant, calls) -> None:
    """Test the firing of events with a sample zha event.

    This test exercises the fast path to validate matching event data.
    """
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "zha_event",
                    "event_data": {
                        "device_ieee": "00:15:8d:00:02:93:04:11",
                        "command": "attribute_updated",
                        "args": {
                            "attribute_id": 0,
                            "attribute_name": "on_off",
                            "value": True,
                        },
                    },
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire(
        "zha_event",
        {
            "device_ieee": "00:15:8d:00:02:93:04:11",
            "unique_id": "00:15:8d:00:02:93:04:11:1:0x0006",
            "endpoint_id": 1,
            "cluster_id": 6,
            "command": "attribute_updated",
            "args": {"attribute_id": 0, "attribute_name": "on_off", "value": True},
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.bus.async_fire(
        "zha_event",
        {
            "device_ieee": "00:15:8d:00:02:93:04:11",
            "unique_id": "00:15:8d:00:02:93:04:11:1:0x0006",
            "endpoint_id": 1,
            "cluster_id": 6,
            "command": "attribute_updated",
            "args": {"attribute_id": 0, "attribute_name": "on_off", "value": False},
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_not_fires_if_event_data_not_matches(
    hass: HomeAssistant, calls
) -> None:
    """Test firing of event if no data match."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {"some_attr": "some_value"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event", {"some_attr": "some_other_value"})
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_not_fires_if_event_context_not_matches(
    hass: HomeAssistant, calls, context_with_user
) -> None:
    """Test firing of event if no context match."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "context": {"user_id": "some_user"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event", {}, context=context_with_user)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_fires_on_multiple_user_ids(
    hass: HomeAssistant, calls, context_with_user
) -> None:
    """Test the firing of event when the trigger has multiple user ids.

    This test exercises the slow path of using vol.Schema to validate
    matching event context.
    """
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {},
                    "context": {"user_id": [context_with_user.user_id, "another id"]},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event", {}, context=context_with_user)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_event_data_with_list(hass: HomeAssistant, calls) -> None:
    """Test the (non)firing of event when the data schema has lists."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {"some_attr": [1, 2]},
                    "context": {},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event", {"some_attr": [1, 2]})
    await hass.async_block_till_done()
    assert len(calls) == 1

    # don't match a single value
    hass.bus.async_fire("test_event", {"some_attr": 1})
    await hass.async_block_till_done()
    assert len(calls) == 1

    # don't match a containing list
    hass.bus.async_fire("test_event", {"some_attr": [1, 2, 3]})
    await hass.async_block_till_done()
    assert len(calls) == 1
