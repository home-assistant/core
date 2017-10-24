"""The tests for the Input number component."""
# pylint: disable=protected-access
import asyncio
import unittest

from homeassistant.core import CoreState, State
from homeassistant.setup import setup_component, async_setup_component
from homeassistant.components.input_number import (DOMAIN, set_value)

from tests.common import get_test_home_assistant, mock_restore_cache


class TestInputNumber(unittest.TestCase):
    """Test the input number component."""

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
                'initial': 50,
                'min': 0,
                'max': 100,
            },
        }}))
        entity_id = 'input_number.test_1'

        state = self.hass.states.get(entity_id)
        self.assertEqual(50, float(state.state))

        set_value(self.hass, entity_id, '30.4')
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual(30.4, float(state.state))

        set_value(self.hass, entity_id, '70')
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual(70, float(state.state))

        set_value(self.hass, entity_id, '110')
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual(70, float(state.state))

    def test_mode(self):
        """Test mode settings."""
        self.assertTrue(
            setup_component(self.hass, DOMAIN, {DOMAIN: {
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
            }}))

        state = self.hass.states.get('input_number.test_default_slider')
        assert state
        self.assertEqual('slider', state.attributes['mode'])

        state = self.hass.states.get('input_number.test_explicit_box')
        assert state
        self.assertEqual('box', state.attributes['mode'])

        state = self.hass.states.get('input_number.test_explicit_slider')
        assert state
        self.assertEqual('slider', state.attributes['mode'])


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
