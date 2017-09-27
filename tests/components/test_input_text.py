"""The tests for the Input text component."""
# pylint: disable=protected-access
import asyncio
import unittest

from homeassistant.core import CoreState, State
from homeassistant.setup import setup_component, async_setup_component
from homeassistant.components.input_text import (DOMAIN, set_value)

from tests.common import get_test_home_assistant, mock_restore_cache


class TestInputText(unittest.TestCase):
    """Test the input slider component."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Setup things to be run when tests are started."""
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
