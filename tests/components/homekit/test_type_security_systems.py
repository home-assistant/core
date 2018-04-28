"""Test different accessory types: Security Systems."""
import unittest

from homeassistant.core import callback
from homeassistant.components.homekit.type_security_systems import (
    SecuritySystem)
from homeassistant.const import (
    ATTR_CODE, ATTR_SERVICE, ATTR_SERVICE_DATA, EVENT_CALL_SERVICE,
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT, STATE_ALARM_DISARMED, STATE_UNKNOWN)

from tests.common import get_test_home_assistant


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
        acp = 'alarm_control_panel.test'

        acc = SecuritySystem(self.hass, 'SecuritySystem', acp,
                             2, config={ATTR_CODE: '1234'})
        acc.run()

        self.assertEqual(acc.aid, 2)
        self.assertEqual(acc.category, 11)  # AlarmSystem

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

        self.hass.states.set(acp, STATE_UNKNOWN)
        self.hass.block_till_done()
        self.assertEqual(acc.char_target_state.value, 3)
        self.assertEqual(acc.char_current_state.value, 3)

        # Set from HomeKit
        acc.char_target_state.client_update_value(0)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], 'alarm_arm_home')
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE_DATA][ATTR_CODE], '1234')
        self.assertEqual(acc.char_target_state.value, 0)

        acc.char_target_state.client_update_value(1)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[1].data[ATTR_SERVICE], 'alarm_arm_away')
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE_DATA][ATTR_CODE], '1234')
        self.assertEqual(acc.char_target_state.value, 1)

        acc.char_target_state.client_update_value(2)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[2].data[ATTR_SERVICE], 'alarm_arm_night')
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE_DATA][ATTR_CODE], '1234')
        self.assertEqual(acc.char_target_state.value, 2)

        acc.char_target_state.client_update_value(3)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[3].data[ATTR_SERVICE], 'alarm_disarm')
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE_DATA][ATTR_CODE], '1234')
        self.assertEqual(acc.char_target_state.value, 3)

    def test_no_alarm_code(self):
        """Test accessory if security_system doesn't require a alarm_code."""
        acp = 'alarm_control_panel.test'

        acc = SecuritySystem(self.hass, 'SecuritySystem', acp,
                             2, config={ATTR_CODE: None})
        # Set from HomeKit
        acc.char_target_state.client_update_value(0)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], 'alarm_arm_home')
        self.assertNotIn(ATTR_CODE, self.events[0].data[ATTR_SERVICE_DATA])
        self.assertEqual(acc.char_target_state.value, 0)

        acc = SecuritySystem(self.hass, 'SecuritySystem', acp,
                             2, config={})
        # Set from HomeKit
        acc.char_target_state.client_update_value(0)
        self.hass.block_till_done()
        self.assertEqual(
            self.events[0].data[ATTR_SERVICE], 'alarm_arm_home')
        self.assertNotIn(ATTR_CODE, self.events[0].data[ATTR_SERVICE_DATA])
        self.assertEqual(acc.char_target_state.value, 0)
