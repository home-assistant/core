"""The tests the custom cards component."""
# pylint: disable=protected-access
import unittest
import logging

from homeassistant.setup import setup_component
from homeassistant.components.custom_card import DOMAIN

from tests.common import get_test_home_assistant

_LOGGER = logging.getLogger(__name__)


class TestCustomCard(unittest.TestCase):
    """Test the custom card module."""

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
            {'noCardsDefined': None},
            {'moreInfoOnly': {'more_info_card': 'test-card'}},
        ]

        for cfg in invalid_configs:
            self.assertFalse(
                setup_component(self.hass, DOMAIN, {DOMAIN: cfg}))

    def test_config_options(self):
        """Test configuration options."""
        count_start = len(self.hass.states.entity_ids())

        _LOGGER.debug('ENTITIES @ start: %s', self.hass.states.entity_ids())

        self.assertTrue(setup_component(self.hass, DOMAIN, {DOMAIN: {
            'test_1': {
                'full_card': 'full-card',
            },
            'test_2': {
                'state_card': 'state-card',
            },
            'test_3': {
                'full_card': 'full-card',
                'state_card': 'state-card',
                'more_info_card': 'more-info-card',
            },
        }}))

        _LOGGER.debug('ENTITIES: %s', self.hass.states.entity_ids())

        self.assertEqual(count_start + 3, len(self.hass.states.entity_ids()))

        state_1 = self.hass.states.get('custom_card.test_1')
        state_2 = self.hass.states.get('custom_card.test_2')
        state_3 = self.hass.states.get('custom_card.test_3')

        self.assertIsNotNone(state_1)
        self.assertIsNotNone(state_2)
        self.assertIsNotNone(state_3)

        self.assertEqual('full-card', state_1.state)
        self.assertEqual('state-card', state_2.state)
        self.assertEqual('full-card', state_3.state)

        self.assertEqual('custom_ui_full-card',
                         state_3.attributes.get('full_card'))
        self.assertEqual('custom_ui_state-card',
                         state_3.attributes.get('state_card'))
        self.assertEqual('custom_ui_more-info-card',
                         state_3.attributes.get('more_info_card'))
