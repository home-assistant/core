"""The tests for the input_boolean component."""
# pylint: disable=protected-access
import asyncio
import unittest
import logging

from homeassistant.core import CoreState, State
from homeassistant.setup import setup_component, async_setup_component
from homeassistant.components.input_boolean import (
    DOMAIN, is_on, toggle, turn_off, turn_on, CONF_INITIAL)
from homeassistant.const import (
    STATE_ON, STATE_OFF, ATTR_ICON, ATTR_FRIENDLY_NAME)

from tests.common import (
    get_test_home_assistant, mock_component, mock_restore_cache)

_LOGGER = logging.getLogger(__name__)


class TestInputBoolean(unittest.TestCase):
    """Test the input boolean module."""

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
            1,
            {},
            {'name with space': None},
        ]

        for cfg in invalid_configs:
            self.assertFalse(
                setup_component(self.hass, DOMAIN, {DOMAIN: cfg}))

    def test_methods(self):
        """Test is_on, turn_on, turn_off methods."""
        self.assertTrue(setup_component(self.hass, DOMAIN, {DOMAIN: {
            'test_1': None,
        }}))
        entity_id = 'input_boolean.test_1'

        self.assertFalse(
            is_on(self.hass, entity_id))

        turn_on(self.hass, entity_id)

        self.hass.block_till_done()

        self.assertTrue(
            is_on(self.hass, entity_id))

        turn_off(self.hass, entity_id)

        self.hass.block_till_done()

        self.assertFalse(
            is_on(self.hass, entity_id))

        toggle(self.hass, entity_id)

        self.hass.block_till_done()

        self.assertTrue(is_on(self.hass, entity_id))

    def test_config_options(self):
        """Test configuration options."""
        count_start = len(self.hass.states.entity_ids())

        _LOGGER.debug('ENTITIES @ start: %s', self.hass.states.entity_ids())

        self.assertTrue(setup_component(self.hass, DOMAIN, {DOMAIN: {
            'test_1': None,
            'test_2': {
                'name': 'Hello World',
                'icon': 'mdi:work',
                'initial': True,
            },
        }}))

        _LOGGER.debug('ENTITIES: %s', self.hass.states.entity_ids())

        self.assertEqual(count_start + 2, len(self.hass.states.entity_ids()))

        state_1 = self.hass.states.get('input_boolean.test_1')
        state_2 = self.hass.states.get('input_boolean.test_2')

        self.assertIsNotNone(state_1)
        self.assertIsNotNone(state_2)

        self.assertEqual(STATE_OFF, state_1.state)
        self.assertNotIn(ATTR_ICON, state_1.attributes)
        self.assertNotIn(ATTR_FRIENDLY_NAME, state_1.attributes)

        self.assertEqual(STATE_ON, state_2.state)
        self.assertEqual('Hello World',
                         state_2.attributes.get(ATTR_FRIENDLY_NAME))
        self.assertEqual('mdi:work', state_2.attributes.get(ATTR_ICON))


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
