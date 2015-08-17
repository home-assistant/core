"""
tests.test_helpers
~~~~~~~~~~~~~~~~~~~~

Tests component helpers.
"""
# pylint: disable=protected-access,too-many-public-methods
import unittest

from common import get_test_home_assistant

import homeassistant.core as ha
import homeassistant.loader as loader
from homeassistant.const import STATE_ON, STATE_OFF, ATTR_ENTITY_ID
from homeassistant.helpers import extract_entity_ids


class TestComponentsCore(unittest.TestCase):
    """ Tests homeassistant.components module. """

    def setUp(self):  # pylint: disable=invalid-name
        """ Init needed objects. """
        self.hass = get_test_home_assistant()
        loader.prepare(self.hass)

        self.hass.states.set('light.Bowl', STATE_ON)
        self.hass.states.set('light.Ceiling', STATE_OFF)
        self.hass.states.set('light.Kitchen', STATE_OFF)

        loader.get_component('group').setup_group(
            self.hass, 'test', ['light.Ceiling', 'light.Kitchen'])

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_extract_entity_ids(self):
        """ Test extract_entity_ids method. """
        call = ha.ServiceCall('light', 'turn_on',
                              {ATTR_ENTITY_ID: 'light.Bowl'})

        self.assertEqual(['light.bowl'],
                         extract_entity_ids(self.hass, call))

        call = ha.ServiceCall('light', 'turn_on',
                              {ATTR_ENTITY_ID: 'group.test'})

        self.assertEqual(['light.ceiling', 'light.kitchen'],
                         extract_entity_ids(self.hass, call))
