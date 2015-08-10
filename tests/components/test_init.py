"""
tests.test_component_core
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests core compoments.
"""
# pylint: disable=protected-access,too-many-public-methods
import unittest

import homeassistant as ha
import homeassistant.loader as loader
from homeassistant.const import (
    STATE_ON, STATE_OFF, SERVICE_TURN_ON, SERVICE_TURN_OFF)
import homeassistant.components as comps


class TestComponentsCore(unittest.TestCase):
    """ Tests homeassistant.components module. """

    def setUp(self):  # pylint: disable=invalid-name
        """ Init needed objects. """
        self.hass = ha.HomeAssistant()
        loader.prepare(self.hass)
        self.assertTrue(comps.setup(self.hass, {}))

        self.hass.states.set('light.Bowl', STATE_ON)
        self.hass.states.set('light.Ceiling', STATE_OFF)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_is_on(self):
        """ Test is_on method. """
        self.assertTrue(comps.is_on(self.hass, 'light.Bowl'))
        self.assertFalse(comps.is_on(self.hass, 'light.Ceiling'))
        self.assertTrue(comps.is_on(self.hass))

    def test_turn_on(self):
        """ Test turn_on method. """
        runs = []
        self.hass.services.register(
            'light', SERVICE_TURN_ON, lambda x: runs.append(1))

        comps.turn_on(self.hass, 'light.Ceiling')

        self.hass.pool.block_till_done()

        self.assertEqual(1, len(runs))

    def test_turn_off(self):
        """ Test turn_off method. """
        runs = []
        self.hass.services.register(
            'light', SERVICE_TURN_OFF, lambda x: runs.append(1))

        comps.turn_off(self.hass, 'light.Bowl')

        self.hass.pool.block_till_done()

        self.assertEqual(1, len(runs))
