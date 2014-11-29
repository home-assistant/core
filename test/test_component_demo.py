"""
test.test_component_demo
~~~~~~~~~~~~~~~~~~~~~~~~

Tests demo component.
"""
# pylint: disable=too-many-public-methods,protected-access
import unittest
import datetime as dt

import ephem

import homeassistant as ha
import homeassistant.components.demo as demo
from homeassistant.components import (
    SERVICE_TURN_ON, SERVICE_TURN_OFF, STATE_ON, STATE_OFF, ATTR_ENTITY_ID)


class TestDemo(unittest.TestCase):
    """ Test the demo module. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_services(self):
        """ Test the demo services. """
        # Test turning on and off different types
        demo.setup(self.hass, {})

        for domain in ('light', 'switch'):
            # Focus on 1 entity
            entity_id = self.hass.get_entity_ids(domain)[0]

            self.hass.call_service(
                domain, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id})

            self.hass._pool.block_till_done()

            self.assertEqual(STATE_ON, self.hass.states.get(entity_id).state)

            self.hass.call_service(
                domain, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id})

            self.hass._pool.block_till_done()

            self.assertEqual(STATE_OFF, self.hass.states.get(entity_id).state)

            # Act on all
            self.hass.call_service(domain, SERVICE_TURN_ON)

            self.hass._pool.block_till_done()

            for entity_id in self.hass.get_entity_ids(domain):
                self.assertEqual(
                    STATE_ON, self.hass.states.get(entity_id).state)

            self.hass.call_service(domain, SERVICE_TURN_OFF)

            self.hass._pool.block_till_done()

            for entity_id in self.hass.get_entity_ids(domain):
                self.assertEqual(
                    STATE_OFF, self.hass.states.get(entity_id).state)

    def test_hiding_demo_state(self):
        """ Test if you can hide the demo card. """
        demo.setup(self.hass, {demo.DOMAIN: {'hide_demo_state': '1'}})

        self.assertIsNone(self.hass.states.get('a.Demo_Mode'))

        demo.setup(self.hass, {demo.DOMAIN: {'hide_demo_state': '0'}})

        self.assertIsNotNone(self.hass.states.get('a.Demo_Mode'))
