"""The tests for the Input number component."""
# pylint: disable=protected-access
import asyncio

from homeassistant.core import CoreState, State, Context
from homeassistant.components.input_number import (
    ATTR_VALUE, DOMAIN, SERVICE_DECREMENT, SERVICE_INCREMENT,
    SERVICE_SET_VALUE)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.loader import bind_hass
from homeassistant.setup import async_setup_component

from tests.common import mock_restore_cache


@bind_hass
def set_value(hass, entity_id, value):
    """Set input_number to value.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.async_create_task(hass.services.async_call(
        DOMAIN, SERVICE_SET_VALUE, {
            ATTR_ENTITY_ID: entity_id,
            ATTR_VALUE: value,
        }))


@bind_hass
def increment(hass, entity_id):
    """Increment value of entity.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.async_create_task(hass.services.async_call(
        DOMAIN, SERVICE_INCREMENT, {
            ATTR_ENTITY_ID: entity_id
        }))


@bind_hass
def decrement(hass, entity_id):
    """Decrement value of entity.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.async_create_task(hass.services.async_call(
        DOMAIN, SERVICE_DECREMENT, {
            ATTR_ENTITY_ID: entity_id
        }))


async def test_config(hass):
    """Test config."""
    invalid_configs = [
        None,
        {},
        {'name with space': None},
        {'test_1': {
            'min': 50,
            'max': 50,
        }},
    ]
    for cfg in invalid_configs:
        assert not await async_setup_component(hass, DOMAIN, {DOMAIN: cfg})


async def test_set_value(hass):
    """Test set_value method."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {
        'test_1': {
            'initial': 50,
            'min': 0,
            'max': 100,
        },
    }})
    entity_id = 'input_number.test_1'

    state = hass.states.get(entity_id)
    assert 50 == float(state.state)

    set_value(hass, entity_id, '30.4')
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert 30.4 == float(state.state)

    set_value(hass, entity_id, '70')
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert 70 == float(state.state)

    set_value(hass, entity_id, '110')
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert 70 == float(state.state)


async def test_increment(hass):
    """Test increment method."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {
        'test_2': {
            'initial': 50,
            'min': 0,
            'max': 51,
        },
    }})
    entity_id = 'input_number.test_2'

    state = hass.states.get(entity_id)
    assert 50 == float(state.state)

    increment(hass, entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert 51 == float(state.state)

    increment(hass, entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert 51 == float(state.state)


async def test_decrement(hass):
    """Test decrement method."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {
        'test_3': {
            'initial': 50,
            'min': 49,
            'max': 100,
        },
    }})
    entity_id = 'input_number.test_3'

    state = hass.states.get(entity_id)
    assert 50 == float(state.state)

    decrement(hass, entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert 49 == float(state.state)

    decrement(hass, entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert 49 == float(state.state)


async def test_mode(hass):
    """Test mode settings."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {
            'test_default_slider': {
                'min': 0,
                'max': 100,
            },
            'test_explicit_box': {
                'min': 0,
                'max': 100,
                'mode': 'box',
            },
            'test_explicit_slider': {
                'min': 0,
                'max': 100,
                'mode': 'slider',
            },
        }})

    state = hass.states.get('input_number.test_default_slider')
    assert state
    assert 'slider' == state.attributes['mode']

    state = hass.states.get('input_number.test_explicit_box')
    assert state
    assert 'box' == state.attributes['mode']

    state = hass.states.get('input_number.test_explicit_slider')
    assert state
    assert 'slider' == state.attributes['mode']


@asyncio.coroutine
def test_restore_state(hass):
    """Ensure states are restored on startup."""
    mock_restore_cache(hass, (
        State('input_number.b1', '70'),
        State('input_number.b2', '200'),
    ))

    hass.state = CoreState.starting

    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            'b1': {
                'min': 0,
                'max': 100,
            },
            'b2': {
                'min': 10,
                'max': 100,
            },
        }})

    state = hass.states.get('input_number.b1')
    assert state
    assert float(state.state) == 70

    state = hass.states.get('input_number.b2')
    assert state
    assert float(state.state) == 10


@asyncio.coroutine
def test_initial_state_overrules_restore_state(hass):
    """Ensure states are restored on startup."""
    mock_restore_cache(hass, (
        State('input_number.b1', '70'),
        State('input_number.b2', '200'),
    ))

    hass.state = CoreState.starting

    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            'b1': {
                'initial': 50,
                'min': 0,
                'max': 100,
            },
            'b2': {
                'initial': 60,
                'min': 0,
                'max': 100,
            },
        }})

    state = hass.states.get('input_number.b1')
    assert state
    assert float(state.state) == 50

    state = hass.states.get('input_number.b2')
    assert state
    assert float(state.state) == 60


@asyncio.coroutine
def test_no_initial_state_and_no_restore_state(hass):
    """Ensure that entity is create without initial and restore feature."""
    hass.state = CoreState.starting

    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            'b1': {
                'min': 0,
                'max': 100,
            },
        }})

    state = hass.states.get('input_number.b1')
    assert state
    assert float(state.state) == 0


async def test_input_number_context(hass, hass_admin_user):
    """Test that input_number context works."""
    assert await async_setup_component(hass, 'input_number', {
        'input_number': {
            'b1': {
                'min': 0,
                'max': 100,
            },
        }
    })

    state = hass.states.get('input_number.b1')
    assert state is not None

    await hass.services.async_call('input_number', 'increment', {
        'entity_id': state.entity_id,
    }, True, Context(user_id=hass_admin_user.id))

    state2 = hass.states.get('input_number.b1')
    assert state2 is not None
    assert state.state != state2.state
    assert state2.context.user_id == hass_admin_user.id
