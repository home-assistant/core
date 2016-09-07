"""The tests for the Input select component."""
# pylint: disable=too-many-public-methods,protected-access
import unittest

import voluptuous as vol

from homeassistant.components import input_select
from homeassistant.const import (
    ATTR_ICON, ATTR_FRIENDLY_NAME)

from tests.common import get_test_home_assistant


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
        with self.assertRaises(vol.Invalid):
            input_select.PLATFORM_SCHEMA(None)
        with self.assertRaises(vol.Invalid):
            input_select.PLATFORM_SCHEMA({})
        with self.assertRaises(vol.Invalid):
            input_select.PLATFORM_SCHEMA({'name with space': None})
        with self.assertRaises(vol.Invalid):
            input_select.PLATFORM_SCHEMA({
                'hello': {
                    'options': None
                }
            })

    def test_select_option(self):
        """Test select_option methods."""
        self.assertTrue(input_select.setup(self.hass, {
            'input_select': {
                'test_1': {
                    'options': [
                        'some option',
                        'another option',
                    ],
                },
            }
        }))
        entity_id = 'input_select.test_1'

        state = self.hass.states.get(entity_id)
        self.assertEqual('some option', state.state)

        input_select.select_option(self.hass, entity_id, 'another option')
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual('another option', state.state)

        input_select.select_option(self.hass, entity_id, 'non existing option')
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

        self.assertTrue(input_select.setup(self.hass, {
            'input_select': input_select.PLATFORM_SCHEMA({
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
            })
        }))

        self.assertEqual(count_start + 2, len(self.hass.states.entity_ids()))

        state_1 = self.hass.states.get('input_select.test_1')
        state_2 = self.hass.states.get('input_select.test_2')

        self.assertIsNotNone(state_1)
        self.assertIsNotNone(state_2)

        self.assertEqual('1', state_1.state)
        self.assertEqual(['1', '2'],
                         state_1.attributes.get(input_select.ATTR_OPTIONS))
        self.assertNotIn(ATTR_ICON, state_1.attributes)

        self.assertEqual('Better Option', state_2.state)
        self.assertEqual(test_2_options,
                         state_2.attributes.get(input_select.ATTR_OPTIONS))
        self.assertEqual('Hello World',
                         state_2.attributes.get(ATTR_FRIENDLY_NAME))
        self.assertEqual('mdi:work', state_2.attributes.get(ATTR_ICON))
