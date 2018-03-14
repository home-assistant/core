"""Test different accessory types: Switches."""
import unittest
from unittest.mock import patch

from homeassistant.core import callback
from homeassistant.components.homekit.switches import Switch
from homeassistant.const import ATTR_SERVICE, EVENT_CALL_SERVICE

from tests.common import get_test_home_assistant
from tests.mock.homekit import get_patch_paths, mock_preload_service

PATH_ACC, PATH_FILE = get_patch_paths('switches')


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
        switch = 'switch.testswitch'

        with patch(PATH_ACC, side_effect=mock_preload_service):
            with patch(PATH_FILE, side_effect=mock_preload_service):
                acc = Switch(self.hass, switch, 'Switch')
                acc.run()

        self.assertEqual(acc.char_on.value, False)

        self.hass.states.set(switch, 'on')
        self.hass.block_till_done()
        self.assertEqual(acc.char_on.value, True)

        self.hass.states.set(switch, 'off')
        self.hass.block_till_done()
        self.assertEqual(acc.char_on.value, False)

        # Set from HomeKit
        acc.char_on.set_value(True)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], 'turn_on')
        self.assertEqual(acc.char_on.value, True)

        acc.char_on.set_value(False)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE], 'turn_off')
        self.assertEqual(acc.char_on.value, False)
