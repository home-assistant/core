"""
tests.test_helpers
~~~~~~~~~~~~~~~~~~~~

Tests component helpers.
"""
# pylint: disable=protected-access,too-many-public-methods
import unittest

import homeassistant.core as ha
from homeassistant import loader, helpers
from homeassistant.const import STATE_ON, STATE_OFF, ATTR_ENTITY_ID

from tests.common import get_test_home_assistant


class TestComponentsCore(unittest.TestCase):
    """ Tests homeassistant.components module. """

    def setUp(self):  # pylint: disable=invalid-name
        """ Init needed objects. """
        self.hass = get_test_home_assistant()

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
                         helpers.extract_entity_ids(self.hass, call))

        call = ha.ServiceCall('light', 'turn_on',
                              {ATTR_ENTITY_ID: 'group.test'})

        self.assertEqual(['light.ceiling', 'light.kitchen'],
                         helpers.extract_entity_ids(self.hass, call))

    def test_extract_domain_configs(self):
        config = {
            'zone': None,
            'zoner': None,
            'zone ': None,
            'zone Hallo': None,
            'zone 100': None,
        }

        self.assertEqual(set(['zone', 'zone Hallo', 'zone 100']),
                         set(helpers.extract_domain_configs(config, 'zone')))
