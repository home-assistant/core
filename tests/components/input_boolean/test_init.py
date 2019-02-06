"""The tests for the input_boolean component."""
# pylint: disable=protected-access
import asyncio
import logging

from homeassistant.core import CoreState, State, Context
from homeassistant.setup import async_setup_component
from homeassistant.components.input_boolean import (
    is_on, CONF_INITIAL, DOMAIN)
from homeassistant.const import (
    STATE_ON, STATE_OFF, ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, ATTR_ICON,
    SERVICE_TOGGLE, SERVICE_TURN_OFF, SERVICE_TURN_ON)

from tests.common import mock_component, mock_restore_cache

_LOGGER = logging.getLogger(__name__)


async def test_config(hass):
    """Test config."""
    invalid_configs = [
        None,
        1,
        {},
        {'name with space': None},
    ]

    for cfg in invalid_configs:
        assert not await async_setup_component(hass, DOMAIN, {DOMAIN: cfg})


async def test_methods(hass):
    """Test is_on, turn_on, turn_off methods."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {
        'test_1': None,
    }})
    entity_id = 'input_boolean.test_1'

    assert not is_on(hass, entity_id)

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id})

    await hass.async_block_till_done()

    assert is_on(hass, entity_id)

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id})

    await hass.async_block_till_done()

    assert not is_on(hass, entity_id)

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: entity_id})

    await hass.async_block_till_done()

    assert is_on(hass, entity_id)


async def test_config_options(hass):
    """Test configuration options."""
    count_start = len(hass.states.async_entity_ids())

    _LOGGER.debug('ENTITIES @ start: %s', hass.states.async_entity_ids())

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {
        'test_1': None,
        'test_2': {
            'name': 'Hello World',
            'icon': 'mdi:work',
            'initial': True,
        },
    }})

    _LOGGER.debug('ENTITIES: %s', hass.states.async_entity_ids())

    assert count_start + 2 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get('input_boolean.test_1')
    state_2 = hass.states.get('input_boolean.test_2')

    assert state_1 is not None
    assert state_2 is not None

    assert STATE_OFF == state_1.state
    assert ATTR_ICON not in state_1.attributes
    assert ATTR_FRIENDLY_NAME not in state_1.attributes

    assert STATE_ON == state_2.state
    assert 'Hello World' == \
        state_2.attributes.get(ATTR_FRIENDLY_NAME)
    assert 'mdi:work' == state_2.attributes.get(ATTR_ICON)


@asyncio.coroutine
def test_restore_state(hass):
    """Ensure states are restored on startup."""
    mock_restore_cache(hass, (
        State('input_boolean.b1', 'on'),
        State('input_boolean.b2', 'off'),
        State('input_boolean.b3', 'on'),
    ))

    hass.state = CoreState.starting
    mock_component(hass, 'recorder')

    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            'b1': None,
            'b2': None,
        }})

    state = hass.states.get('input_boolean.b1')
    assert state
    assert state.state == 'on'

    state = hass.states.get('input_boolean.b2')
    assert state
    assert state.state == 'off'


@asyncio.coroutine
def test_initial_state_overrules_restore_state(hass):
    """Ensure states are restored on startup."""
    mock_restore_cache(hass, (
        State('input_boolean.b1', 'on'),
        State('input_boolean.b2', 'off'),
    ))

    hass.state = CoreState.starting

    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            'b1': {CONF_INITIAL: False},
            'b2': {CONF_INITIAL: True},
        }})

    state = hass.states.get('input_boolean.b1')
    assert state
    assert state.state == 'off'

    state = hass.states.get('input_boolean.b2')
    assert state
    assert state.state == 'on'


async def test_input_boolean_context(hass, hass_admin_user):
    """Test that input_boolean context works."""
    assert await async_setup_component(hass, 'input_boolean', {
        'input_boolean': {
            'ac': {CONF_INITIAL: True},
        }
    })

    state = hass.states.get('input_boolean.ac')
    assert state is not None

    await hass.services.async_call('input_boolean', 'turn_off', {
        'entity_id': state.entity_id,
    }, True, Context(user_id=hass_admin_user.id))

    state2 = hass.states.get('input_boolean.ac')
    assert state2 is not None
    assert state.state != state2.state
    assert state2.context.user_id == hass_admin_user.id
