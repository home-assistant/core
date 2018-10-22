"""The tests for the Input text component."""
# pylint: disable=protected-access
import asyncio
import unittest

from homeassistant.components.input_text import (
    ATTR_VALUE, DOMAIN, SERVICE_SET_VALUE)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import CoreState, State, Context
from homeassistant.loader import bind_hass
from homeassistant.setup import setup_component, async_setup_component

from tests.common import get_test_home_assistant, mock_restore_cache


@bind_hass
def set_value(hass, entity_id, value):
    """Set input_text to value.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.services.call(DOMAIN, SERVICE_SET_VALUE, {
        ATTR_ENTITY_ID: entity_id,
        ATTR_VALUE: value,
    })


class TestInputText(unittest.TestCase):
    """Test the input slider component."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_config(self):
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
            self.assertFalse(
                setup_component(self.hass, DOMAIN, {DOMAIN: cfg}))

    def test_set_value(self):
        """Test set_value method."""
        self.assertTrue(setup_component(self.hass, DOMAIN, {DOMAIN: {
            'test_1': {
                'initial': 'test',
                'min': 3,
                'max': 10,
            },
        }}))
        entity_id = 'input_text.test_1'

        state = self.hass.states.get(entity_id)
        self.assertEqual('test', str(state.state))

        set_value(self.hass, entity_id, 'testing')
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual('testing', str(state.state))

        set_value(self.hass, entity_id, 'testing too long')
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual('testing', str(state.state))

    def test_mode(self):
        """Test mode settings."""
        self.assertTrue(
            setup_component(self.hass, DOMAIN, {DOMAIN: {
                'test_default_text': {
                    'initial': 'test',
                    'min': 3,
                    'max': 10,
                },
                'test_explicit_text': {
                    'initial': 'test',
                    'min': 3,
                    'max': 10,
                    'mode': 'text',
                },
                'test_explicit_password': {
                    'initial': 'test',
                    'min': 3,
                    'max': 10,
                    'mode': 'password',
                },
            }}))

        state = self.hass.states.get('input_text.test_default_text')
        assert state
        self.assertEqual('text', state.attributes['mode'])

        state = self.hass.states.get('input_text.test_explicit_text')
        assert state
        self.assertEqual('text', state.attributes['mode'])

        state = self.hass.states.get('input_text.test_explicit_password')
        assert state
        self.assertEqual('password', state.attributes['mode'])


@asyncio.coroutine
def test_restore_state(hass):
    """Ensure states are restored on startup."""
    mock_restore_cache(hass, (
        State('input_text.b1', 'test'),
        State('input_text.b2', 'testing too long'),
    ))

    hass.state = CoreState.starting

    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            'b1': {
                'min': 0,
                'max': 10,
            },
            'b2': {
                'min': 0,
                'max': 10,
            },
        }})

    state = hass.states.get('input_text.b1')
    assert state
    assert str(state.state) == 'test'

    state = hass.states.get('input_text.b2')
    assert state
    assert str(state.state) == 'unknown'


@asyncio.coroutine
def test_initial_state_overrules_restore_state(hass):
    """Ensure states are restored on startup."""
    mock_restore_cache(hass, (
        State('input_text.b1', 'testing'),
        State('input_text.b2', 'testing too long'),
    ))

    hass.state = CoreState.starting

    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            'b1': {
                'initial': 'test',
                'min': 0,
                'max': 10,
            },
            'b2': {
                'initial': 'test',
                'min': 0,
                'max': 10,
            },
        }})

    state = hass.states.get('input_text.b1')
    assert state
    assert str(state.state) == 'test'

    state = hass.states.get('input_text.b2')
    assert state
    assert str(state.state) == 'test'


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

    state = hass.states.get('input_text.b1')
    assert state
    assert str(state.state) == 'unknown'


async def test_input_text_context(hass):
    """Test that input_text context works."""
    assert await async_setup_component(hass, 'input_text', {
        'input_text': {
            't1': {
                'initial': 'bla',
            }
        }
    })

    state = hass.states.get('input_text.t1')
    assert state is not None

    await hass.services.async_call('input_text', 'set_value', {
        'entity_id': state.entity_id,
        'value': 'new_value',
    }, True, Context(user_id='abcd'))

    state2 = hass.states.get('input_text.t1')
    assert state2 is not None
    assert state.state != state2.state
    assert state2.context.user_id == 'abcd'
