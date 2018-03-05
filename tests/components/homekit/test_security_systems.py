"""Test different accessory types: Security Systems."""
import unittest
from unittest.mock import patch

from homeassistant.core import callback
from homeassistant.components.homekit.security_systems import SecuritySystem
from homeassistant.const import (
    ATTR_SERVICE, EVENT_CALL_SERVICE,
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT, STATE_ALARM_DISARMED)

from tests.common import get_test_home_assistant
from tests.mock.homekit import get_patch_paths, mock_preload_service

PATH_ACC, PATH_FILE = get_patch_paths('security_systems')


class TestHomekitSecuritySystems(unittest.TestCase):
    """Test class for all accessory types regarding security systems."""

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
        acp = 'alarm_control_panel.testsecurity'

        with patch(PATH_ACC, side_effect=mock_preload_service):
            with patch(PATH_FILE, side_effect=mock_preload_service):
                acc = SecuritySystem(self.hass, acp, 'SecuritySystem')
                acc.run()

        self.assertEqual(acc.char_current_state.value, 3)
        self.assertEqual(acc.char_target_state.value, 3)

        self.hass.states.set(acp, STATE_ALARM_ARMED_AWAY)
        self.hass.block_till_done()
        self.assertEqual(acc.char_target_state.value, 1)
        self.assertEqual(acc.char_current_state.value, 1)

        self.hass.states.set(acp, STATE_ALARM_ARMED_HOME)
        self.hass.block_till_done()
        self.assertEqual(acc.char_target_state.value, 0)
        self.assertEqual(acc.char_current_state.value, 0)

        self.hass.states.set(acp, STATE_ALARM_ARMED_NIGHT)
        self.hass.block_till_done()
        self.assertEqual(acc.char_target_state.value, 2)
        self.assertEqual(acc.char_current_state.value, 2)

        self.hass.states.set(acp, STATE_ALARM_DISARMED)
        self.hass.block_till_done()
        self.assertEqual(acc.char_target_state.value, 3)
        self.assertEqual(acc.char_current_state.value, 3)

        # Set from HomeKit
        acc.char_target_state.set_value(0)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], 'alarm_arm_home')
        self.assertEqual(acc.char_target_state.value, 0)

        acc.char_target_state.set_value(1)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE], 'alarm_arm_away')
        self.assertEqual(acc.char_target_state.value, 1)

        acc.char_target_state.set_value(2)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[2].data[ATTR_SERVICE], 'alarm_arm_night')
        self.assertEqual(acc.char_target_state.value, 2)

        acc.char_target_state.set_value(3)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[3].data[ATTR_SERVICE], 'alarm_disarm')
        self.assertEqual(acc.char_target_state.value, 3)
