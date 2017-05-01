"""The tests for the Input select component."""
# pylint: disable=protected-access
import asyncio
import unittest

from tests.common import get_test_home_assistant, mock_restore_cache

from homeassistant.core import State
from homeassistant.setup import setup_component, async_setup_component
from homeassistant.components.input_select import (
    ATTR_OPTIONS, DOMAIN, SERVICE_SET_OPTIONS,
    select_option, select_next, select_previous)
from homeassistant.const import (
    ATTR_ICON, ATTR_FRIENDLY_NAME)


class TestInputSelect(unittest.TestCase):
    """Test the input select component."""

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
            # {'bad_options': {'options': None}},
            {'bad_initial': {
                'options': [1, 2],
                'initial': 3,
            }},
        ]

        for cfg in invalid_configs:
            self.assertFalse(
                setup_component(self.hass, DOMAIN, {DOMAIN: cfg}))

    def test_select_option(self):
        """Test select_option methods."""
        self.assertTrue(
            setup_component(self.hass, DOMAIN, {DOMAIN: {
                'test_1': {
                    'options': [
                        'some option',
                        'another option',
                    ],
                },
            }}))
        entity_id = 'input_select.test_1'

        state = self.hass.states.get(entity_id)
        self.assertEqual('some option', state.state)

        select_option(self.hass, entity_id, 'another option')
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual('another option', state.state)

        select_option(self.hass, entity_id, 'non existing option')
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual('another option', state.state)

    def test_select_next(self):
        """Test select_next methods."""
        self.assertTrue(
            setup_component(self.hass, DOMAIN, {DOMAIN: {
                'test_1': {
                    'options': [
                        'first option',
                        'middle option',
                        'last option',
                    ],
                    'initial': 'middle option',
                },
            }}))
        entity_id = 'input_select.test_1'

        state = self.hass.states.get(entity_id)
        self.assertEqual('middle option', state.state)

        select_next(self.hass, entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual('last option', state.state)

        select_next(self.hass, entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual('first option', state.state)

    def test_select_previous(self):
        """Test select_previous methods."""
        self.assertTrue(
            setup_component(self.hass, DOMAIN, {DOMAIN: {
                'test_1': {
                    'options': [
                        'first option',
                        'middle option',
                        'last option',
                    ],
                    'initial': 'middle option',
                },
            }}))
        entity_id = 'input_select.test_1'

        state = self.hass.states.get(entity_id)
        self.assertEqual('middle option', state.state)

        select_previous(self.hass, entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual('first option', state.state)

        select_previous(self.hass, entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual('last option', state.state)

    def test_config_options(self):
        """Test configuration options."""
        count_start = len(self.hass.states.entity_ids())

        test_2_options = [
            'Good Option',
            'Better Option',
            'Best Option',
        ]

        self.assertTrue(setup_component(self.hass, DOMAIN, {
            DOMAIN: {
                'test_1': {
                    'options': [
                        1,
                        2,
                    ],
                },
                'test_2': {
                    'name': 'Hello World',
                    'icon': 'mdi:work',
                    'options': test_2_options,
                    'initial': 'Better Option',
                },
            }
        }))

        self.assertEqual(count_start + 2, len(self.hass.states.entity_ids()))

        state_1 = self.hass.states.get('input_select.test_1')
        state_2 = self.hass.states.get('input_select.test_2')

        self.assertIsNotNone(state_1)
        self.assertIsNotNone(state_2)

        self.assertEqual('1', state_1.state)
        self.assertEqual(['1', '2'],
                         state_1.attributes.get(ATTR_OPTIONS))
        self.assertNotIn(ATTR_ICON, state_1.attributes)

        self.assertEqual('Better Option', state_2.state)
        self.assertEqual(test_2_options,
                         state_2.attributes.get(ATTR_OPTIONS))
        self.assertEqual('Hello World',
                         state_2.attributes.get(ATTR_FRIENDLY_NAME))
        self.assertEqual('mdi:work', state_2.attributes.get(ATTR_ICON))

    def test_set_options_service(self):
        """Test set_options service."""
        self.assertTrue(
            setup_component(self.hass, DOMAIN, {DOMAIN: {
                'test_1': {
                    'options': [
                        'first option',
                        'middle option',
                        'last option',
                    ],
                    'initial': 'middle option',
                },
            }}))
        entity_id = 'input_select.test_1'

        state = self.hass.states.get(entity_id)
        self.assertEqual('middle option', state.state)

        data = {ATTR_OPTIONS: ["test1", "test2"], "entity_id": entity_id}
        self.hass.services.call(DOMAIN, SERVICE_SET_OPTIONS, data)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual('test1', state.state)

        select_option(self.hass, entity_id, 'first option')
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        self.assertEqual('test1', state.state)

        select_option(self.hass, entity_id, 'test2')
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        self.assertEqual('test2', state.state)


@asyncio.coroutine
def test_restore_state(hass):
    """Ensure states are restored on startup."""
    mock_restore_cache(hass, (
        State('input_select.s1', 'last option'),
        State('input_select.s2', 'bad option'),
    ))

    options = {
        'options': [
            'first option',
            'middle option',
            'last option',
        ],
    }

    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            's1': options,
            's2': options,
        }})

    state = hass.states.get('input_select.s1')
    assert state
    assert state.state == 'last option'

    state = hass.states.get('input_select.s2')
    assert state
    assert state.state == 'first option'


@asyncio.coroutine
def test_initial_state_overrules_restore_state(hass):
    """Ensure states are restored on startup."""
    mock_restore_cache(hass, (
        State('input_select.s1', 'last option'),
        State('input_select.s2', 'bad option'),
    ))

    options = {
        'options': [
            'first option',
            'middle option',
            'last option',
        ],
        'initial': 'middle option',
    }

    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            's1': options,
            's2': options,
        }})

    state = hass.states.get('input_select.s1')
    assert state
    assert state.state == 'middle option'

    state = hass.states.get('input_select.s2')
    assert state
    assert state.state == 'middle option'
