"""Test different accessory types: Covers."""
import unittest

from homeassistant.core import callback
from homeassistant.components.cover import (
    ATTR_POSITION, ATTR_CURRENT_POSITION, SUPPORT_STOP)
from homeassistant.const import (
    STATE_CLOSED, STATE_UNAVAILABLE, STATE_UNKNOWN, STATE_OPEN,
    ATTR_SERVICE, ATTR_SERVICE_DATA, EVENT_CALL_SERVICE,
    ATTR_SUPPORTED_FEATURES)

from tests.common import get_test_home_assistant
from tests.components.homekit.test_accessories import patch_debounce


class TestHomekitCovers(unittest.TestCase):
    """Test class for all accessory types regarding covers."""

    @classmethod
    def setUpClass(cls):
        """Setup Light class import and debounce patcher."""
        cls.patcher = patch_debounce()
        cls.patcher.start()
        _import = __import__('homeassistant.components.homekit.type_covers',
                             fromlist=['GarageDoorOpener', 'WindowCovering,',
                                       'WindowCoveringBasic'])
        cls.garage_cls = _import.GarageDoorOpener
        cls.window_cls = _import.WindowCovering
        cls.window_basic_cls = _import.WindowCoveringBasic

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

    def test_garage_door_open_close(self):
        """Test if accessory and HA are updated accordingly."""
        garage_door = 'cover.garage_door'

        acc = self.garage_cls(self.hass, 'Cover', garage_door, 2, config=None)
        acc.run()

        self.assertEqual(acc.aid, 2)
        self.assertEqual(acc.category, 4)  # GarageDoorOpener

        self.assertEqual(acc.char_current_state.value, 0)
        self.assertEqual(acc.char_target_state.value, 0)

        self.hass.states.set(garage_door, STATE_CLOSED)
        self.hass.block_till_done()

        self.assertEqual(acc.char_current_state.value, 1)
        self.assertEqual(acc.char_target_state.value, 1)

        self.hass.states.set(garage_door, STATE_OPEN)
        self.hass.block_till_done()

        self.assertEqual(acc.char_current_state.value, 0)
        self.assertEqual(acc.char_target_state.value, 0)

        self.hass.states.set(garage_door, STATE_UNAVAILABLE)
        self.hass.block_till_done()

        self.assertEqual(acc.char_current_state.value, 0)
        self.assertEqual(acc.char_target_state.value, 0)

        self.hass.states.set(garage_door, STATE_UNKNOWN)
        self.hass.block_till_done()

        self.assertEqual(acc.char_current_state.value, 0)
        self.assertEqual(acc.char_target_state.value, 0)

        # Set closed from HomeKit
        acc.char_target_state.client_update_value(1)
        self.hass.block_till_done()

        self.assertEqual(acc.char_current_state.value, 2)
        self.assertEqual(acc.char_target_state.value, 1)
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], 'close_cover')

        self.hass.states.set(garage_door, STATE_CLOSED)
        self.hass.block_till_done()

        # Set open from HomeKit
        acc.char_target_state.client_update_value(0)
        self.hass.block_till_done()

        self.assertEqual(acc.char_current_state.value, 3)
        self.assertEqual(acc.char_target_state.value, 0)
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE], 'open_cover')

    def test_window_set_cover_position(self):
        """Test if accessory and HA are updated accordingly."""
        window_cover = 'cover.window'

        acc = self.window_cls(self.hass, 'Cover', window_cover, 2, config=None)
        acc.run()

        self.assertEqual(acc.aid, 2)
        self.assertEqual(acc.category, 14)  # WindowCovering

        self.assertEqual(acc.char_current_position.value, 0)
        self.assertEqual(acc.char_target_position.value, 0)

        self.hass.states.set(window_cover, STATE_UNKNOWN,
                             {ATTR_CURRENT_POSITION: None})
        self.hass.block_till_done()

        self.assertEqual(acc.char_current_position.value, 0)
        self.assertEqual(acc.char_target_position.value, 0)

        self.hass.states.set(window_cover, STATE_OPEN,
                             {ATTR_CURRENT_POSITION: 50})
        self.hass.block_till_done()

        self.assertEqual(acc.char_current_position.value, 50)
        self.assertEqual(acc.char_target_position.value, 50)

        # Set from HomeKit
        acc.char_target_position.client_update_value(25)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], 'set_cover_position')
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE_DATA][ATTR_POSITION], 25)

        self.assertEqual(acc.char_current_position.value, 50)
        self.assertEqual(acc.char_target_position.value, 25)

        # Set from HomeKit
        acc.char_target_position.client_update_value(75)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE], 'set_cover_position')
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE_DATA][ATTR_POSITION], 75)

        self.assertEqual(acc.char_current_position.value, 50)
        self.assertEqual(acc.char_target_position.value, 75)

    def test_window_open_close(self):
        """Test if accessory and HA are updated accordingly."""
        window_cover = 'cover.window'

        self.hass.states.set(window_cover, STATE_UNKNOWN,
                             {ATTR_SUPPORTED_FEATURES: 0})
        acc = self.window_basic_cls(self.hass, 'Cover', window_cover, 2,
                                    config=None)
        acc.run()

        self.assertEqual(acc.aid, 2)
        self.assertEqual(acc.category, 14)  # WindowCovering

        self.assertEqual(acc.char_current_position.value, 0)
        self.assertEqual(acc.char_target_position.value, 0)
        self.assertEqual(acc.char_position_state.value, 2)

        self.hass.states.set(window_cover, STATE_UNKNOWN)
        self.hass.block_till_done()

        self.assertEqual(acc.char_current_position.value, 0)
        self.assertEqual(acc.char_target_position.value, 0)
        self.assertEqual(acc.char_position_state.value, 2)

        self.hass.states.set(window_cover, STATE_OPEN)
        self.hass.block_till_done()

        self.assertEqual(acc.char_current_position.value, 100)
        self.assertEqual(acc.char_target_position.value, 100)
        self.assertEqual(acc.char_position_state.value, 2)

        self.hass.states.set(window_cover, STATE_CLOSED)
        self.hass.block_till_done()

        self.assertEqual(acc.char_current_position.value, 0)
        self.assertEqual(acc.char_target_position.value, 0)
        self.assertEqual(acc.char_position_state.value, 2)

        # Set from HomeKit
        acc.char_target_position.client_update_value(25)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], 'close_cover')

        self.assertEqual(acc.char_current_position.value, 0)
        self.assertEqual(acc.char_target_position.value, 0)
        self.assertEqual(acc.char_position_state.value, 2)

        # Set from HomeKit
        acc.char_target_position.client_update_value(90)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE], 'open_cover')

        self.assertEqual(acc.char_current_position.value, 100)
        self.assertEqual(acc.char_target_position.value, 100)
        self.assertEqual(acc.char_position_state.value, 2)

        # Set from HomeKit
        acc.char_target_position.client_update_value(55)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[2].data[ATTR_SERVICE], 'open_cover')

        self.assertEqual(acc.char_current_position.value, 100)
        self.assertEqual(acc.char_target_position.value, 100)
        self.assertEqual(acc.char_position_state.value, 2)

    def test_window_open_close_stop(self):
        """Test if accessory and HA are updated accordingly."""
        window_cover = 'cover.window'

        self.hass.states.set(window_cover, STATE_UNKNOWN,
                             {ATTR_SUPPORTED_FEATURES: SUPPORT_STOP})
        acc = self.window_basic_cls(self.hass, 'Cover', window_cover, 2,
                                    config=None)
        acc.run()

        # Set from HomeKit
        acc.char_target_position.client_update_value(25)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], 'close_cover')

        self.assertEqual(acc.char_current_position.value, 0)
        self.assertEqual(acc.char_target_position.value, 0)
        self.assertEqual(acc.char_position_state.value, 2)

        # Set from HomeKit
        acc.char_target_position.client_update_value(90)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE], 'open_cover')

        self.assertEqual(acc.char_current_position.value, 100)
        self.assertEqual(acc.char_target_position.value, 100)
        self.assertEqual(acc.char_position_state.value, 2)

        # Set from HomeKit
        acc.char_target_position.client_update_value(55)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[2].data[ATTR_SERVICE], 'stop_cover')

        self.assertEqual(acc.char_current_position.value, 50)
        self.assertEqual(acc.char_target_position.value, 50)
        self.assertEqual(acc.char_position_state.value, 2)
