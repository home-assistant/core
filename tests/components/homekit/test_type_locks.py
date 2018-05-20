"""Test different accessory types: Locks."""
import unittest

from homeassistant.core import callback
from homeassistant.components.homekit.type_locks import Lock
from homeassistant.const import (
    STATE_UNKNOWN, STATE_UNLOCKED, STATE_LOCKED,
    ATTR_SERVICE, EVENT_CALL_SERVICE)

from tests.common import get_test_home_assistant


class TestHomekitSensors(unittest.TestCase):
    """Test class for all accessory types regarding covers."""

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

    def test_lock_unlock(self):
        """Test if accessory and HA are updated accordingly."""
        kitchen_lock = 'lock.kitchen_door'

        acc = Lock(self.hass, 'Lock', kitchen_lock, 2, config=None)
        acc.run()

        self.assertEqual(acc.aid, 2)
        self.assertEqual(acc.category, 6)  # DoorLock

        self.assertEqual(acc.char_current_state.value, 3)
        self.assertEqual(acc.char_target_state.value, 1)

        self.hass.states.set(kitchen_lock, STATE_LOCKED)
        self.hass.block_till_done()

        self.assertEqual(acc.char_current_state.value, 1)
        self.assertEqual(acc.char_target_state.value, 1)

        self.hass.states.set(kitchen_lock, STATE_UNLOCKED)
        self.hass.block_till_done()

        self.assertEqual(acc.char_current_state.value, 0)
        self.assertEqual(acc.char_target_state.value, 0)

        self.hass.states.set(kitchen_lock, STATE_UNKNOWN)
        self.hass.block_till_done()

        self.assertEqual(acc.char_current_state.value, 3)
        self.assertEqual(acc.char_target_state.value, 0)

        # Set from HomeKit
        acc.char_target_state.client_update_value(1)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], 'lock')
        self.assertEqual(acc.char_target_state.value, 1)

        acc.char_target_state.client_update_value(0)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE], 'unlock')
        self.assertEqual(acc.char_target_state.value, 0)

        self.hass.states.remove(kitchen_lock)
        self.hass.block_till_done()
