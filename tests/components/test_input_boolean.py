"""The tests for the input_boolean component."""
# pylint: disable=too-many-public-methods,protected-access
import unittest

from homeassistant.components import input_boolean
from homeassistant.const import (
    STATE_ON, STATE_OFF, ATTR_ICON, ATTR_FRIENDLY_NAME)

from tests.common import get_test_home_assistant


class TestInputBoolean(unittest.TestCase):
    """Test the input boolean module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_config(self):
        """Test config."""
        self.assertFalse(input_boolean.setup(self.hass, {
            'input_boolean': None
        }))

        self.assertFalse(input_boolean.setup(self.hass, {
            'input_boolean': {
            }
        }))

        self.assertFalse(input_boolean.setup(self.hass, {
            'input_boolean': {
                'name with space': None
            }
        }))

    def test_methods(self):
        """Test is_on, turn_on, turn_off methods."""
        self.assertTrue(input_boolean.setup(self.hass, {
            'input_boolean': {
                'test_1': None,
            }
        }))
        entity_id = 'input_boolean.test_1'

        self.assertFalse(
            input_boolean.is_on(self.hass, entity_id))

        input_boolean.turn_on(self.hass, entity_id)

        self.hass.block_till_done()

        self.assertTrue(
            input_boolean.is_on(self.hass, entity_id))

        input_boolean.turn_off(self.hass, entity_id)

        self.hass.block_till_done()

        self.assertFalse(
            input_boolean.is_on(self.hass, entity_id))

        input_boolean.toggle(self.hass, entity_id)

        self.hass.block_till_done()

        self.assertTrue(
            input_boolean.is_on(self.hass, entity_id))

    def test_config_options(self):
        """Test configuration options."""
        count_start = len(self.hass.states.entity_ids())

        self.assertTrue(input_boolean.setup(self.hass, {
            'input_boolean': {
                'test_1': None,
                'test_2': {
                    'name': 'Hello World',
                    'icon': 'work',
                    'initial': True,
                },
            },
        }))

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
        self.assertEqual('work', state_2.attributes.get(ATTR_ICON))
