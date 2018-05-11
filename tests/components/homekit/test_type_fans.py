"""Test different accessory types: Fans."""
import unittest

from homeassistant.core import callback
from homeassistant.components.fan import (
    ATTR_DIRECTION, ATTR_OSCILLATING, ATTR_SPEED, ATTR_SPEED_LIST,
    DIRECTION_FORWARD, DIRECTION_REVERSE, DOMAIN, SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION, SUPPORT_DIRECTION, SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED)
from homeassistant.const import (
    ATTR_DOMAIN, ATTR_ENTITY_ID, ATTR_SERVICE, ATTR_SERVICE_DATA,
    ATTR_SUPPORTED_FEATURES, EVENT_CALL_SERVICE, SERVICE_TURN_ON,
    SERVICE_TURN_OFF, STATE_ON, STATE_OFF, STATE_UNKNOWN)

from tests.common import get_test_home_assistant
from tests.components.homekit.test_accessories import patch_debounce


class TestHomekitFans(unittest.TestCase):
    """Test class for all accessory types regarding fans."""

    @classmethod
    def setUpClass(cls):
        """Setup Light class import and debounce patcher."""
        cls.patcher = patch_debounce()
        cls.patcher.start()
        _import = __import__('homeassistant.components.homekit.type_fans',
                             fromlist=['Fan'])
        cls.fan_cls = _import.Fan

    @classmethod
    def tearDownClass(cls):
        """Stop debounce patcher."""
        cls.patcher.stop()

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.events = []

        @callback
        def record_event(event):
            """Track called event."""
            self.events.append(event)

        self.hass.bus.listen(EVENT_CALL_SERVICE, record_event)

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_fan_basic(self):
        """Test fan with char state."""
        entity_id = 'fan.demo'

        self.hass.states.set(entity_id, STATE_ON,
                             {ATTR_SUPPORTED_FEATURES: 0})
        self.hass.block_till_done()
        acc = self.fan_cls(self.hass, 'Fan', entity_id, 2, config=None)
        self.assertEqual(acc.aid, 2)
        self.assertEqual(acc.category, 3)  # Fan
        self.assertEqual(acc.char_active.value, 0)

        acc.run()
        self.hass.block_till_done()
        self.assertEqual(acc.char_active.value, 1)

        self.hass.states.set(entity_id, STATE_OFF,
                             {ATTR_SUPPORTED_FEATURES: 0})
        self.hass.block_till_done()
        self.assertEqual(acc.char_active.value, 0)

        self.hass.states.set(entity_id, STATE_UNKNOWN)
        self.hass.block_till_done()
        self.assertEqual(acc.char_active.value, 0)

        # Set from HomeKit
        acc.char_active.client_update_value(1)
        self.hass.block_till_done()
        self.assertEqual(self.events[0].data[ATTR_DOMAIN], DOMAIN)
        self.assertEqual(self.events[0].data[ATTR_SERVICE], SERVICE_TURN_ON)

        self.hass.states.set(entity_id, STATE_ON)
        self.hass.block_till_done()

        acc.char_active.client_update_value(0)
        self.hass.block_till_done()
        self.assertEqual(self.events[1].data[ATTR_DOMAIN], DOMAIN)
        self.assertEqual(self.events[1].data[ATTR_SERVICE], SERVICE_TURN_OFF)

        self.hass.states.set(entity_id, STATE_OFF)
        self.hass.block_till_done()

        # Remove entity
        self.hass.states.remove(entity_id)
        self.hass.block_till_done()

    def test_fan_speed(self):
        """Test fan with speed."""
        entity_id = 'fan.demo'

        self.hass.states.set(entity_id, STATE_ON, {
            ATTR_SUPPORTED_FEATURES: SUPPORT_SET_SPEED,
            ATTR_SPEED_LIST: ['low', 'medium', 'high', 'max'],
            ATTR_SPEED: 'low'})
        self.hass.block_till_done()
        acc = self.fan_cls(self.hass, 'Fan', entity_id, 2, config=None)
        self.assertEqual(acc.char_speed.value, 0)

        acc.run()
        self.hass.block_till_done()
        self.assertEqual(acc.char_speed.value, 25)

        self.hass.states.set(entity_id, STATE_ON, {ATTR_SPEED: 'medium'})
        self.hass.block_till_done()
        self.assertEqual(acc.char_speed.value, 50)

        # Set from HomeKit
        acc.char_speed.client_update_value(75)
        self.hass.block_till_done()
        self.assertEqual(self.events[0].data[ATTR_DOMAIN], DOMAIN)
        self.assertEqual(self.events[0].data[ATTR_SERVICE], SERVICE_TURN_ON)
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE_DATA], {
                ATTR_ENTITY_ID: entity_id, ATTR_SPEED: 'high'})

        acc.char_speed.client_update_value(100)
        self.hass.block_till_done()
        self.assertEqual(self.events[1].data[ATTR_DOMAIN], DOMAIN)
        self.assertEqual(self.events[1].data[ATTR_SERVICE], SERVICE_TURN_ON)
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE_DATA], {
                ATTR_ENTITY_ID: entity_id, ATTR_SPEED: 'max'})

        acc.char_speed.client_update_value(0)
        self.hass.block_till_done()
        self.assertEqual(self.events[2].data[ATTR_DOMAIN], DOMAIN)
        self.assertEqual(self.events[2].data[ATTR_SERVICE], SERVICE_TURN_OFF)

    def test_fan_direction(self):
        """Test fan with direction."""
        entity_id = 'fan.demo'

        self.hass.states.set(entity_id, STATE_ON, {
            ATTR_SUPPORTED_FEATURES: SUPPORT_DIRECTION})
        self.hass.block_till_done()
        acc = self.fan_cls(self.hass, 'Fan', entity_id, 2, config=None)
        self.assertEqual(acc.char_direction.value, 0)

        acc.run()
        self.hass.block_till_done()
        self.assertEqual(acc.char_direction.value, 0)

        self.hass.states.set(entity_id, STATE_ON, {ATTR_DIRECTION: 'reverse'})
        self.hass.block_till_done()
        self.assertEqual(acc.char_direction.value, 1)

        # Set from HomeKit
        acc.char_direction.client_update_value(0)
        self.hass.block_till_done()
        self.assertEqual(self.events[0].data[ATTR_DOMAIN], DOMAIN)
        self.assertEqual(self.events[0].data[ATTR_SERVICE], SERVICE_SET_DIRECTION)
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE_DATA], {
                ATTR_ENTITY_ID: entity_id, ATTR_DIRECTION: 'forward'})

        acc.char_direction.client_update_value(1)
        self.hass.block_till_done()
        self.assertEqual(self.events[1].data[ATTR_DOMAIN], DOMAIN)
        self.assertEqual(self.events[1].data[ATTR_SERVICE], SERVICE_SET_DIRECTION)
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE_DATA], {
                ATTR_ENTITY_ID: entity_id, ATTR_DIRECTION: 'reverse'})

    def test_fan_oscillate(self):
        """Test fan with oscillate."""
        entity_id = 'fan.demo'

        self.hass.states.set(entity_id, STATE_ON, {
            ATTR_SUPPORTED_FEATURES: SUPPORT_OSCILLATE})
        self.hass.block_till_done()
        acc = self.fan_cls(self.hass, 'Fan', entity_id, 2, config=None)
        self.assertEqual(acc.char_swing.value, 0)

        acc.run()
        self.hass.block_till_done()
        self.assertEqual(acc.char_swing.value, False)

        self.hass.states.set(entity_id, STATE_ON, {ATTR_OSCILLATING: True})
        self.hass.block_till_done()
        self.assertEqual(acc.char_swing.value, 1)

        # Set from HomeKit
        acc.char_swing.client_update_value(0)
        self.hass.block_till_done()
        self.assertEqual(self.events[0].data[ATTR_DOMAIN], DOMAIN)
        self.assertEqual(self.events[0].data[ATTR_SERVICE], SERVICE_OSCILLATE)
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE_DATA], {
                ATTR_ENTITY_ID: entity_id, ATTR_OSCILLATING: 'false'})

        acc.char_swing.client_update_value(1)
        self.hass.block_till_done()
        self.assertEqual(self.events[1].data[ATTR_DOMAIN], DOMAIN)
        self.assertEqual(self.events[1].data[ATTR_SERVICE], SERVICE_OSCILLATE)
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE_DATA], {
                ATTR_ENTITY_ID: entity_id, ATTR_OSCILLATING: 'true'})
