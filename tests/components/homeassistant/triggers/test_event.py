"""The tests for the Event automation."""
import pytest

import homeassistant.components.automation as automation
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, SERVICE_TURN_OFF
from homeassistant.core import Context
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service, mock_component


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, "group")


async def test_if_fires_on_event(hass, calls):
    """Test the firing of events."""
    context = Context()

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


async def test_if_fires_on_event_extra_data(hass, calls):
    """Test the firing of events still matches with event data."""
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

    hass.bus.async_fire("test_event", {"extra_key": "extra_data"})
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


async def test_if_fires_on_event_with_data(hass, calls):
    """Test the firing of events with data."""
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
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire(
        "test_event",
        {"some_attr": "some_value", "another": "value", "second_attr": "second_value"},
    )
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.bus.async_fire("test_event", {"some_attr": "some_value", "another": "value"})
    await hass.async_block_till_done()
    assert len(calls) == 1  # No new call


async def test_if_fires_on_event_with_empty_data_config(hass, calls):
    """Test the firing of events with empty data config.

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
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event", {"some_attr": "some_value", "another": "value"})
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_event_with_nested_data(hass, calls):
    """Test the firing of events with nested data."""
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


async def test_if_not_fires_if_event_data_not_matches(hass, calls):
    """Test firing of event if no match."""
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
