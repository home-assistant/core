"""The tests for the input_boolean component."""
# pylint: disable=too-many-public-methods,protected-access
import unittest
import logging

from tests.common import get_test_home_assistant

from homeassistant.bootstrap import setup_component
from homeassistant.components.input_boolean import (
    DOMAIN, is_on, toggle, turn_off, turn_on)
from homeassistant.const import (
    STATE_ON, STATE_OFF, ATTR_ICON, ATTR_FRIENDLY_NAME)

_LOGGER = logging.getLogger(__name__)


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
