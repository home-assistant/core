"""Test different accessory types: Switches."""
import unittest

from homeassistant.core import callback, split_entity_id
from homeassistant.components.homekit.type_switches import Switch
from homeassistant.const import (
    ATTR_DOMAIN, ATTR_SERVICE, EVENT_CALL_SERVICE,
    SERVICE_TURN_ON, SERVICE_TURN_OFF, STATE_ON, STATE_OFF)

from tests.common import get_test_home_assistant


class TestHomekitSwitches(unittest.TestCase):
    """Test class for all accessory types regarding switches."""

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

    def test_switch_set_state(self):
        """Test if accessory and HA are updated accordingly."""
        entity_id = 'switch.test'
        domain = split_entity_id(entity_id)[0]

        acc = Switch(self.hass, entity_id, 'Switch', aid=2)
        acc.run()

        self.assertEqual(acc.aid, 2)
        self.assertEqual(acc.category, 8)  # Switch

        self.assertEqual(acc.char_on.value, False)

        self.hass.states.set(entity_id, STATE_ON)
        self.hass.block_till_done()
        self.assertEqual(acc.char_on.value, True)

        self.hass.states.set(entity_id, STATE_OFF)
        self.hass.block_till_done()
        self.assertEqual(acc.char_on.value, False)

        # Set from HomeKit
        acc.char_on.set_value(True)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_DOMAIN], domain)
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], SERVICE_TURN_ON)

        acc.char_on.set_value(False)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[1].data[ATTR_DOMAIN], domain)
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE], SERVICE_TURN_OFF)

    def test_remote_set_state(self):
        """Test service call for remote as domain."""
        entity_id = 'remote.test'
        domain = split_entity_id(entity_id)[0]

        acc = Switch(self.hass, entity_id, 'Switch', aid=2)
        acc.run()

        self.assertEqual(acc.char_on.value, False)

        # Set from HomeKit
        acc.char_on.set_value(True)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_DOMAIN], domain)
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], SERVICE_TURN_ON)
        self.assertEqual(acc.char_on.value, True)

    def test_input_boolean_set_state(self):
        """Test service call for remote as domain."""
        entity_id = 'input_boolean.test'
        domain = split_entity_id(entity_id)[0]

        acc = Switch(self.hass, entity_id, 'Switch', aid=2)
        acc.run()

        self.assertEqual(acc.char_on.value, False)

        # Set from HomeKit
        acc.char_on.set_value(True)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_DOMAIN], domain)
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], SERVICE_TURN_ON)
        self.assertEqual(acc.char_on.value, True)
