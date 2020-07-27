"""The tests for numeric state automation."""
from datetime import timedelta

import pytest
import voluptuous as vol

import homeassistant.components.automation as automation
from homeassistant.components.automation import numeric_state
from homeassistant.core import Context
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
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


async def test_if_fires_on_entity_change_below(hass, calls):
    """Test the firing with changed entity."""
    context = Context()
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "below": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    # 9 is below 10
    hass.states.async_set("test.entity", 9, context=context)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].context.parent_id == context.id

    # Set above 12 so the automation will fire again
    hass.states.async_set("test.entity", 12)
    await common.async_turn_off(hass)
    await hass.async_block_till_done()
    hass.states.async_set("test.entity", 9)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_entity_change_over_to_below(hass, calls):
    """Test the firing with changed entity."""
    hass.states.async_set("test.entity", 11)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "below": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # 9 is below 10
    hass.states.async_set("test.entity", 9)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_entities_change_over_to_below(hass, calls):
    """Test the firing with changed entities."""
    hass.states.async_set("test.entity_1", 11)
    hass.states.async_set("test.entity_2", 11)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": ["test.entity_1", "test.entity_2"],
                    "below": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # 9 is below 10
    hass.states.async_set("test.entity_1", 9)
    await hass.async_block_till_done()
    assert len(calls) == 1
    hass.states.async_set("test.entity_2", 9)
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_if_not_fires_on_entity_change_below_to_below(hass, calls):
    """Test the firing with changed entity."""
    context = Context()
    hass.states.async_set("test.entity", 11)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "below": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # 9 is below 10 so this should fire
    hass.states.async_set("test.entity", 9, context=context)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].context.parent_id == context.id

    # already below so should not fire again
    hass.states.async_set("test.entity", 5)
    await hass.async_block_till_done()
    assert len(calls) == 1

    # still below so should not fire again
    hass.states.async_set("test.entity", 3)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_not_below_fires_on_entity_change_to_equal(hass, calls):
    """Test the firing with changed entity."""
    hass.states.async_set("test.entity", 11)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "below": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # 10 is not below 10 so this should not fire again
    hass.states.async_set("test.entity", 10)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_fires_on_initial_entity_below(hass, calls):
    """Test the firing when starting with a match."""
    hass.states.async_set("test.entity", 9)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "below": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # Fire on first update even if initial state was already below
    hass.states.async_set("test.entity", 8)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_initial_entity_above(hass, calls):
    """Test the firing when starting with a match."""
    hass.states.async_set("test.entity", 11)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "above": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # Fire on first update even if initial state was already above
    hass.states.async_set("test.entity", 12)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_entity_change_above(hass, calls):
    """Test the firing with changed entity."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "above": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    # 11 is above 10
    hass.states.async_set("test.entity", 11)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_entity_change_below_to_above(hass, calls):
    """Test the firing with changed entity."""
    # set initial state
    hass.states.async_set("test.entity", 9)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "above": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # 11 is above 10 and 9 is below
    hass.states.async_set("test.entity", 11)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_not_fires_on_entity_change_above_to_above(hass, calls):
    """Test the firing with changed entity."""
    # set initial state
    hass.states.async_set("test.entity", 9)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "above": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # 12 is above 10 so this should fire
    hass.states.async_set("test.entity", 12)
    await hass.async_block_till_done()
    assert len(calls) == 1

    # already above, should not fire again
    hass.states.async_set("test.entity", 15)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_not_above_fires_on_entity_change_to_equal(hass, calls):
    """Test the firing with changed entity."""
    # set initial state
    hass.states.async_set("test.entity", 9)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "above": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # 10 is not above 10 so this should not fire again
    hass.states.async_set("test.entity", 10)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_fires_on_entity_change_below_range(hass, calls):
    """Test the firing with changed entity."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "below": 10,
                    "above": 5,
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    # 9 is below 10
    hass.states.async_set("test.entity", 9)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_entity_change_below_above_range(hass, calls):
    """Test the firing with changed entity."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "below": 10,
                    "above": 5,
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    # 4 is below 5
    hass.states.async_set("test.entity", 4)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_fires_on_entity_change_over_to_below_range(hass, calls):
    """Test the firing with changed entity."""
    hass.states.async_set("test.entity", 11)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "below": 10,
                    "above": 5,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # 9 is below 10
    hass.states.async_set("test.entity", 9)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_entity_change_over_to_below_above_range(hass, calls):
    """Test the firing with changed entity."""
    hass.states.async_set("test.entity", 11)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "below": 10,
                    "above": 5,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # 4 is below 5 so it should not fire
    hass.states.async_set("test.entity", 4)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_not_fires_if_entity_not_match(hass, calls):
    """Test if not fired with non matching entity."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.another_entity",
                    "below": 100,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", 11)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_fires_on_entity_change_below_with_attribute(hass, calls):
    """Test attributes change."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "below": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    # 9 is below 10
    hass.states.async_set("test.entity", 9, {"test_attribute": 11})
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_not_fires_on_entity_change_not_below_with_attribute(hass, calls):
    """Test attributes."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "below": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    # 11 is not below 10
    hass.states.async_set("test.entity", 11, {"test_attribute": 9})
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_fires_on_attribute_change_with_attribute_below(hass, calls):
    """Test attributes change."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "value_template": "{{ state.attributes.test_attribute }}",
                    "below": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    # 9 is below 10
    hass.states.async_set("test.entity", "entity", {"test_attribute": 9})
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_not_fires_on_attribute_change_with_attribute_not_below(hass, calls):
    """Test attributes change."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "value_template": "{{ state.attributes.test_attribute }}",
                    "below": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    # 11 is not below 10
    hass.states.async_set("test.entity", "entity", {"test_attribute": 11})
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_not_fires_on_entity_change_with_attribute_below(hass, calls):
    """Test attributes change."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "value_template": "{{ state.attributes.test_attribute }}",
                    "below": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    # 11 is not below 10, entity state value should not be tested
    hass.states.async_set("test.entity", "9", {"test_attribute": 11})
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_not_fires_on_entity_change_with_not_attribute_below(hass, calls):
    """Test attributes change."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "value_template": "{{ state.attributes.test_attribute }}",
                    "below": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    # 11 is not below 10, entity state value should not be tested
    hass.states.async_set("test.entity", "entity")
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_fires_on_attr_change_with_attribute_below_and_multiple_attr(hass, calls):
    """Test attributes change."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "value_template": "{{ state.attributes.test_attribute }}",
                    "below": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    # 9 is not below 10
    hass.states.async_set(
        "test.entity", "entity", {"test_attribute": 9, "not_test_attribute": 11}
    )
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_template_list(hass, calls):
    """Test template list."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "value_template": "{{ state.attributes.test_attribute[2] }}",
                    "below": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    # 3 is below 10
    hass.states.async_set("test.entity", "entity", {"test_attribute": [11, 15, 3]})
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_template_string(hass, calls):
    """Test template string."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "value_template": "{{ state.attributes.test_attribute | multiply(10) }}",
                    "below": 10,
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": "{{ trigger.%s }}"
                        % "}} - {{ trigger.".join(
                            (
                                "platform",
                                "entity_id",
                                "below",
                                "above",
                                "from_state.state",
                                "to_state.state",
                            )
                        )
                    },
                },
            }
        },
    )
    hass.states.async_set("test.entity", "test state 1", {"test_attribute": "1.2"})
    await hass.async_block_till_done()
    hass.states.async_set("test.entity", "test state 2", {"test_attribute": "0.9"})
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert (
        calls[0].data["some"]
        == "numeric_state - test.entity - 10.0 - None - test state 1 - test state 2"
    )


async def test_not_fires_on_attr_change_with_attr_not_below_multiple_attr(hass, calls):
    """Test if not fired changed attributes."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "value_template": "{{ state.attributes.test_attribute }}",
                    "below": 10,
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    # 11 is not below 10
    hass.states.async_set(
        "test.entity", "entity", {"test_attribute": 11, "not_test_attribute": 9}
    )
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_action(hass, calls):
    """Test if action."""
    entity_id = "domain.test_entity"
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "numeric_state",
                    "entity_id": entity_id,
                    "above": 8,
                    "below": 12,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(entity_id, 10)
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()

    assert len(calls) == 1

    hass.states.async_set(entity_id, 8)
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()

    assert len(calls) == 1

    hass.states.async_set(entity_id, 9)
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()

    assert len(calls) == 2


async def test_if_fails_setup_bad_for(hass, calls):
    """Test for setup failure for bad for."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "above": 8,
                    "below": 12,
                    "for": {"invalid": 5},
                },
                "action": {"service": "homeassistant.turn_on"},
            }
        },
    )

    with patch.object(automation.numeric_state, "_LOGGER") as mock_logger:
        hass.states.async_set("test.entity", 9)
        await hass.async_block_till_done()
        assert mock_logger.error.called


async def test_if_fails_setup_for_without_above_below(hass, calls):
    """Test for setup failures for missing above or below."""
    with assert_setup_component(0, automation.DOMAIN):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "numeric_state",
                        "entity_id": "test.entity",
                        "for": {"seconds": 5},
                    },
                    "action": {"service": "homeassistant.turn_on"},
                }
            },
        )


async def test_if_not_fires_on_entity_change_with_for(hass, calls):
    """Test for not firing on entity change with for."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "above": 8,
                    "below": 12,
                    "for": {"seconds": 5},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", 9)
    await hass.async_block_till_done()
    hass.states.async_set("test.entity", 15)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_not_fires_on_entities_change_with_for_after_stop(hass, calls):
    """Test for not firing on entities change with for after stop."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": ["test.entity_1", "test.entity_2"],
                    "above": 8,
                    "below": 12,
                    "for": {"seconds": 5},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity_1", 9)
    hass.states.async_set("test.entity_2", 9)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.states.async_set("test.entity_1", 15)
    hass.states.async_set("test.entity_2", 15)
    await hass.async_block_till_done()
    hass.states.async_set("test.entity_1", 9)
    hass.states.async_set("test.entity_2", 9)
    await hass.async_block_till_done()
    await common.async_turn_off(hass)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_entity_change_with_for_attribute_change(hass, calls):
    """Test for firing on entity change with for and attribute change."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "above": 8,
                    "below": 12,
                    "for": {"seconds": 5},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    utcnow = dt_util.utcnow()
    with patch("homeassistant.core.dt_util.utcnow") as mock_utcnow:
        mock_utcnow.return_value = utcnow
        hass.states.async_set("test.entity", 9)
        await hass.async_block_till_done()
        mock_utcnow.return_value += timedelta(seconds=4)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        hass.states.async_set("test.entity", 9, attributes={"mock_attr": "attr_change"})
        await hass.async_block_till_done()
        assert len(calls) == 0
        mock_utcnow.return_value += timedelta(seconds=4)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        await hass.async_block_till_done()
        assert len(calls) == 1


async def test_if_fires_on_entity_change_with_for(hass, calls):
    """Test for firing on entity change with for."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "above": 8,
                    "below": 12,
                    "for": {"seconds": 5},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", 9)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_wait_template_with_trigger(hass, calls):
    """Test using wait template with 'trigger.entity_id'."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "above": 10,
                },
                "action": [
                    {"wait_template": "{{ states(trigger.entity_id) | int < 10 }}"},
                    {
                        "service": "test.automation",
                        "data_template": {
                            "some": "{{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                ("platform", "entity_id", "to_state.state")
                            )
                        },
                    },
                ],
            }
        },
    )

    await hass.async_block_till_done()

    hass.states.async_set("test.entity", "12")
    hass.states.async_set("test.entity", "8")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert "numeric_state - test.entity - 12" == calls[0].data["some"]


async def test_if_fires_on_entities_change_no_overlap(hass, calls):
    """Test for firing on entities change with no overlap."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": ["test.entity_1", "test.entity_2"],
                    "above": 8,
                    "below": 12,
                    "for": {"seconds": 5},
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {"some": "{{ trigger.entity_id }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    utcnow = dt_util.utcnow()
    with patch("homeassistant.core.dt_util.utcnow") as mock_utcnow:
        mock_utcnow.return_value = utcnow
        hass.states.async_set("test.entity_1", 9)
        await hass.async_block_till_done()
        mock_utcnow.return_value += timedelta(seconds=10)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        await hass.async_block_till_done()
        assert len(calls) == 1
        assert calls[0].data["some"] == "test.entity_1"

        hass.states.async_set("test.entity_2", 9)
        await hass.async_block_till_done()
        mock_utcnow.return_value += timedelta(seconds=10)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        await hass.async_block_till_done()
        assert len(calls) == 2
        assert calls[1].data["some"] == "test.entity_2"


async def test_if_fires_on_entities_change_overlap(hass, calls):
    """Test for firing on entities change with overlap."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": ["test.entity_1", "test.entity_2"],
                    "above": 8,
                    "below": 12,
                    "for": {"seconds": 5},
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {"some": "{{ trigger.entity_id }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    utcnow = dt_util.utcnow()
    with patch("homeassistant.core.dt_util.utcnow") as mock_utcnow:
        mock_utcnow.return_value = utcnow
        hass.states.async_set("test.entity_1", 9)
        await hass.async_block_till_done()
        mock_utcnow.return_value += timedelta(seconds=1)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        hass.states.async_set("test.entity_2", 9)
        await hass.async_block_till_done()
        mock_utcnow.return_value += timedelta(seconds=1)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        hass.states.async_set("test.entity_2", 15)
        await hass.async_block_till_done()
        mock_utcnow.return_value += timedelta(seconds=1)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        hass.states.async_set("test.entity_2", 9)
        await hass.async_block_till_done()
        assert len(calls) == 0
        mock_utcnow.return_value += timedelta(seconds=3)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        await hass.async_block_till_done()
        assert len(calls) == 1
        assert calls[0].data["some"] == "test.entity_1"

        mock_utcnow.return_value += timedelta(seconds=3)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        await hass.async_block_till_done()
        assert len(calls) == 2
        assert calls[1].data["some"] == "test.entity_2"


async def test_if_fires_on_change_with_for_template_1(hass, calls):
    """Test for firing on  change with for template."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "above": 8,
                    "below": 12,
                    "for": {"seconds": "{{ 5 }}"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", 9)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_change_with_for_template_2(hass, calls):
    """Test for firing on  change with for template."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "above": 8,
                    "below": 12,
                    "for": "{{ 5 }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", 9)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_on_change_with_for_template_3(hass, calls):
    """Test for firing on  change with for template."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "above": 8,
                    "below": 12,
                    "for": "00:00:{{ 5 }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", 9)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_invalid_for_template(hass, calls):
    """Test for invalid for template."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": "test.entity",
                    "above": 8,
                    "below": 12,
                    "for": "{{ five }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    with patch.object(automation.numeric_state, "_LOGGER") as mock_logger:
        hass.states.async_set("test.entity", 9)
        await hass.async_block_till_done()
        assert mock_logger.error.called


async def test_if_fires_on_entities_change_overlap_for_template(hass, calls):
    """Test for firing on entities change with overlap and for template."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "numeric_state",
                    "entity_id": ["test.entity_1", "test.entity_2"],
                    "above": 8,
                    "below": 12,
                    "for": '{{ 5 if trigger.entity_id == "test.entity_1"'
                    "   else 10 }}",
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": "{{ trigger.entity_id }} - {{ trigger.for }}"
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()

    utcnow = dt_util.utcnow()
    with patch("homeassistant.util.dt.utcnow") as mock_utcnow:
        mock_utcnow.return_value = utcnow
        hass.states.async_set("test.entity_1", 9)
        await hass.async_block_till_done()
        mock_utcnow.return_value += timedelta(seconds=1)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        hass.states.async_set("test.entity_2", 9)
        await hass.async_block_till_done()
        mock_utcnow.return_value += timedelta(seconds=1)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        hass.states.async_set("test.entity_2", 15)
        await hass.async_block_till_done()
        mock_utcnow.return_value += timedelta(seconds=1)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        hass.states.async_set("test.entity_2", 9)
        await hass.async_block_till_done()
        assert len(calls) == 0
        mock_utcnow.return_value += timedelta(seconds=3)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        await hass.async_block_till_done()
        assert len(calls) == 1
        assert calls[0].data["some"] == "test.entity_1 - 0:00:05"

        mock_utcnow.return_value += timedelta(seconds=3)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        await hass.async_block_till_done()
        assert len(calls) == 1
        mock_utcnow.return_value += timedelta(seconds=5)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        await hass.async_block_till_done()
        assert len(calls) == 2
        assert calls[1].data["some"] == "test.entity_2 - 0:00:10"


def test_below_above():
    """Test above cannot be above below."""
    with pytest.raises(vol.Invalid):
        numeric_state.TRIGGER_SCHEMA(
            {"platform": "numeric_state", "above": 1200, "below": 1000}
        )
