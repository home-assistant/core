"""Test cases around the demo fan platform."""

import unittest

from homeassistant.setup import setup_component
from homeassistant.components import fan
from homeassistant.const import STATE_OFF, STATE_ON

from tests.common import get_test_home_assistant
from tests.components.fan import common

FAN_ENTITY_ID = 'fan.living_room_fan'


class TestDemoFan(unittest.TestCase):
    """Test the fan demo platform."""

    def get_entity(self):
        """Get the fan entity."""
        return self.hass.states.get(FAN_ENTITY_ID)

    def setUp(self):
        """Initialize unit test data."""
        self.hass = get_test_home_assistant()
        self.assertTrue(setup_component(self.hass, fan.DOMAIN, {'fan': {
            'platform': 'demo',
        }}))
        self.hass.block_till_done()

    def tearDown(self):
        """Tear down unit test data."""
        self.hass.stop()

    def test_turn_on(self):
        """Test turning on the device."""
        self.assertEqual(STATE_OFF, self.get_entity().state)

        common.turn_on(self.hass, FAN_ENTITY_ID)
        self.hass.block_till_done()
        self.assertNotEqual(STATE_OFF, self.get_entity().state)

        common.turn_on(self.hass, FAN_ENTITY_ID, fan.SPEED_HIGH)
        self.hass.block_till_done()
        self.assertEqual(STATE_ON, self.get_entity().state)
        self.assertEqual(fan.SPEED_HIGH,
                         self.get_entity().attributes[fan.ATTR_SPEED])

    def test_turn_off(self):
        """Test turning off the device."""
        self.assertEqual(STATE_OFF, self.get_entity().state)

        common.turn_on(self.hass, FAN_ENTITY_ID)
        self.hass.block_till_done()
        self.assertNotEqual(STATE_OFF, self.get_entity().state)

        common.turn_off(self.hass, FAN_ENTITY_ID)
        self.hass.block_till_done()
        self.assertEqual(STATE_OFF, self.get_entity().state)

    def test_turn_off_without_entity_id(self):
        """Test turning off all fans."""
        self.assertEqual(STATE_OFF, self.get_entity().state)

        common.turn_on(self.hass, FAN_ENTITY_ID)
        self.hass.block_till_done()
        self.assertNotEqual(STATE_OFF, self.get_entity().state)

        common.turn_off(self.hass)
        self.hass.block_till_done()
        self.assertEqual(STATE_OFF, self.get_entity().state)

    def test_set_direction(self):
        """Test setting the direction of the device."""
        self.assertEqual(STATE_OFF, self.get_entity().state)

        common.set_direction(self.hass, FAN_ENTITY_ID, fan.DIRECTION_REVERSE)
        self.hass.block_till_done()
        self.assertEqual(fan.DIRECTION_REVERSE,
                         self.get_entity().attributes.get('direction'))

    def test_set_speed(self):
        """Test setting the speed of the device."""
        self.assertEqual(STATE_OFF, self.get_entity().state)

        common.set_speed(self.hass, FAN_ENTITY_ID, fan.SPEED_LOW)
        self.hass.block_till_done()
        self.assertEqual(fan.SPEED_LOW,
                         self.get_entity().attributes.get('speed'))

    def test_oscillate(self):
        """Test oscillating the fan."""
        self.assertFalse(self.get_entity().attributes.get('oscillating'))

        common.oscillate(self.hass, FAN_ENTITY_ID, True)
        self.hass.block_till_done()
        self.assertTrue(self.get_entity().attributes.get('oscillating'))

        common.oscillate(self.hass, FAN_ENTITY_ID, False)
        self.hass.block_till_done()
        self.assertFalse(self.get_entity().attributes.get('oscillating'))

    def test_is_on(self):
        """Test is on service call."""
        self.assertFalse(fan.is_on(self.hass, FAN_ENTITY_ID))

        common.turn_on(self.hass, FAN_ENTITY_ID)
        self.hass.block_till_done()
        self.assertTrue(fan.is_on(self.hass, FAN_ENTITY_ID))
