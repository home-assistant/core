"""The tests for the Input select component."""
# pylint: disable=too-many-public-methods,protected-access
import unittest

from tests.common import get_test_home_assistant

from homeassistant.bootstrap import setup_component
from homeassistant.components.input_select import (
    ATTR_OPTIONS, DOMAIN, select_option)
from homeassistant.const import (
    ATTR_ICON, ATTR_FRIENDLY_NAME)


class TestInputSelect(unittest.TestCase):
    """Test the input select component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
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
