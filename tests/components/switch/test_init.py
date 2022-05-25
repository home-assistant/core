"""The tests for the Switch component."""
from datetime import timedelta

import pytest

from homeassistant import core
from homeassistant.components import switch
from homeassistant.const import CONF_PLATFORM, STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from tests.components.switch import common


@pytest.fixture
def entities(hass):
    """Initialize the test switch."""
    platform = getattr(hass.components, "test.switch")
    platform.init()
    yield platform.ENTITIES


async def test_methods(hass, entities, enable_custom_integrations):
    """Test is_on, turn_on, turn_off methods."""
    switch_1, switch_2, switch_3 = entities
    assert await async_setup_component(
        hass, switch.DOMAIN, {switch.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()
    assert switch.is_on(hass, switch_1.entity_id)
    assert not switch.is_on(hass, switch_2.entity_id)
    assert not switch.is_on(hass, switch_3.entity_id)

    await common.async_turn_off(hass, switch_1.entity_id)
    await common.async_turn_on(hass, switch_2.entity_id)

    assert not switch.is_on(hass, switch_1.entity_id)
    assert switch.is_on(hass, switch_2.entity_id)

    # Turn all off
    await common.async_turn_off(hass)

    assert not switch.is_on(hass, switch_1.entity_id)
    assert not switch.is_on(hass, switch_2.entity_id)
    assert not switch.is_on(hass, switch_3.entity_id)

    # Turn all on
    await common.async_turn_on(hass)

    assert switch.is_on(hass, switch_1.entity_id)
    assert switch.is_on(hass, switch_2.entity_id)
    assert switch.is_on(hass, switch_3.entity_id)


async def test_switch_context(
    hass, entities, hass_admin_user, enable_custom_integrations
):
    """Test that switch context works."""
    assert await async_setup_component(hass, "switch", {"switch": {"platform": "test"}})

    await hass.async_block_till_done()

    state = hass.states.get("switch.ac")
    assert state is not None

    await hass.services.async_call(
        "switch",
        "toggle",
        {"entity_id": state.entity_id},
        True,
        core.Context(user_id=hass_admin_user.id),
    )

    state2 = hass.states.get("switch.ac")
    assert state2 is not None
    assert state.state != state2.state
    assert state2.context.user_id == hass_admin_user.id


async def test_switch_context_filtering(
    hass, hass_admin_user, enable_custom_integrations, freezer
):
    """Test that switch context works."""
    platform = getattr(hass.components, "test.switch")
    platform.init(empty=True)

    platform.ENTITIES.append(
        platform.MockToggleEntity("test1", STATE_ON, optimistic=False)
    )

    entity = platform.ENTITIES[0]
    # Enable forced updates and turn off polling to get full control over state changes
    entity._attr_force_update = True
    entity._attr_should_poll = False

    assert await async_setup_component(hass, "switch", {"switch": {"platform": "test"}})
    await hass.async_block_till_done()

    assert entity.entity_id == "switch.test1"

    state = hass.states.get("switch.test1")
    assert state.state == STATE_ON

    # Turn the switch off when it's on
    context = core.Context(user_id=hass_admin_user.id)
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.test1"},
        True,
        context,
    )
    # Make sure the switch is not optimistic
    prev_state = state
    state = hass.states.get("switch.test1")
    assert state is prev_state

    # Force update state to on, the state change should not be attributed to the context
    prev_state = state
    entity.async_set_state(STATE_ON)
    state = hass.states.get("switch.test1")
    assert state is not prev_state
    assert state.state == STATE_ON
    assert state.context is not context

    # Change state to off, the state change should be attributed to the context
    entity.async_set_state(STATE_OFF)
    state = hass.states.get("switch.test1")
    assert state.state == STATE_OFF
    assert state.context is context

    # Change state back to on, the state change should not be attributed to the context
    entity.async_set_state(STATE_ON)
    state = hass.states.get("switch.test1")
    assert state.state == STATE_ON
    assert state.context is not context

    # Change state to off again, the state change should be attributed to the context
    entity.async_set_state(STATE_OFF)
    state = hass.states.get("switch.test1")
    assert state.state == STATE_OFF
    assert state.context is context

    # Bump time and change state, the state change should not be attributed to the context
    freezer.tick(timedelta(seconds=5.001))
    entity.async_set_state(STATE_OFF)
    state = hass.states.get("switch.test1")
    assert state.state == STATE_OFF
    assert state.context is not context

    # Turn the switch on when it's off
    context = core.Context(user_id=hass_admin_user.id)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.test1"},
        True,
        context,
    )

    # Force update state to off, the state change should not be attributed to the context
    prev_state = state
    entity.async_set_state(STATE_OFF)
    state = hass.states.get("switch.test1")
    assert state is not prev_state
    assert state.state == STATE_OFF
    assert state.context is not context

    # Change state to on, the state change should be attributed to the context
    entity.async_set_state(STATE_ON)
    state = hass.states.get("switch.test1")
    assert state.state == STATE_ON
    assert state.context is context

    # Change state back to off, the state change should not be attributed to the context
    entity.async_set_state(STATE_OFF)
    state = hass.states.get("switch.test1")
    assert state.state == STATE_OFF
    assert state.context is not context

    # Change state to on again, the state change should be attributed to the context
    entity.async_set_state(STATE_ON)
    state = hass.states.get("switch.test1")
    assert state.state == STATE_ON
    assert state.context is context

    # Turn the switch on when it's already on
    context = core.Context(user_id=hass_admin_user.id)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.test1"},
        True,
        context,
    )

    # Force update state to on, the state change should be attributed to the context
    prev_state = state
    entity.async_set_state(STATE_ON)
    state = hass.states.get("switch.test1")
    assert state is not prev_state
    assert state.state == STATE_ON
    assert state.context is context

    # Change state to off, the state change should not be attributed to the context
    entity.async_set_state(STATE_OFF)
    state = hass.states.get("switch.test1")
    assert state.state == STATE_OFF
    assert state.context is not context

    # Change state back to on, the state change should be attributed to the context
    entity.async_set_state(STATE_ON)
    state = hass.states.get("switch.test1")
    assert state.state == STATE_ON
    assert state.context is context

    # Change state to off again, the state change should not be attributed to the context
    entity.async_set_state(STATE_OFF)
    state = hass.states.get("switch.test1")
    assert state.state == STATE_OFF
    assert state.context is not context

    # Turn the switch off when it's already off
    context = core.Context(user_id=hass_admin_user.id)
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.test1"},
        True,
        context,
    )

    # Force update state to off, the state change should be attributed to the context
    prev_state = state
    entity.async_set_state(STATE_OFF)
    state = hass.states.get("switch.test1")
    assert state is not prev_state
    assert state.state == STATE_OFF
    assert state.context is context

    # Change state to on, the state change should not be attributed to the context
    entity.async_set_state(STATE_ON)
    state = hass.states.get("switch.test1")
    assert state.state == STATE_ON
    assert state.context is not context

    # Change state back to off, the state change should be attributed to the context
    entity.async_set_state(STATE_OFF)
    state = hass.states.get("switch.test1")
    assert state.state == STATE_OFF
    assert state.context is context

    # Change state to on again, the state change should not be attributed to the context
    entity.async_set_state(STATE_ON)
    state = hass.states.get("switch.test1")
    assert state.state == STATE_ON
    assert state.context is not context
