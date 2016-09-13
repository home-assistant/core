"""The tests the MQTT alarm control panel component."""
import unittest

from homeassistant.bootstrap import _setup_component
from homeassistant.const import (
    STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED, STATE_UNKNOWN)
from homeassistant.components import alarm_control_panel

from tests.common import (
    mock_mqtt_component, fire_mqtt_message, get_test_home_assistant)

CODE = 'HELLO_CODE'


class TestAlarmControlPanelMQTT(unittest.TestCase):
    """Test the manual alarm module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down stuff we started."""
        self.hass.stop()

    def test_fail_setup_without_state_topic(self):
        """Test for failing with no state topic."""
        self.hass.config.components = ['mqtt']
        assert not _setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'command_topic': 'alarm/command'
            }
        })

    def test_fail_setup_without_command_topic(self):
        """Test failing with no command topic."""
        self.hass.config.components = ['mqtt']
        assert not _setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'state_topic': 'alarm/state'
            }
        })

    def test_update_state_via_state_topic(self):
        """Test updating with via state topic."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
            }
        })

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_UNKNOWN,
                         self.hass.states.get(entity_id).state)

        for state in (STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME,
                      STATE_ALARM_ARMED_AWAY, STATE_ALARM_PENDING,
                      STATE_ALARM_TRIGGERED):
            fire_mqtt_message(self.hass, 'alarm/state', state)
            self.hass.block_till_done()
            self.assertEqual(state, self.hass.states.get(entity_id).state)

    def test_ignore_update_state_if_unknown_via_state_topic(self):
        """Test ignoring updates via state topic."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
            }
        })

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_UNKNOWN,
                         self.hass.states.get(entity_id).state)

        fire_mqtt_message(self.hass, 'alarm/state', 'unsupported state')
        self.hass.block_till_done()
        self.assertEqual(STATE_UNKNOWN, self.hass.states.get(entity_id).state)

    def test_arm_home_publishes_mqtt(self):
        """Test publishing of MQTT messages while armed."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
            }
        })

        alarm_control_panel.alarm_arm_home(self.hass)
        self.hass.block_till_done()
        self.assertEqual(('alarm/command', 'ARM_HOME', 0, False),
                         self.mock_publish.mock_calls[-1][1])

    def test_arm_home_not_publishes_mqtt_with_invalid_code(self):
        """Test not publishing of MQTT messages with invalid code."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
                'code': '1234'
            }
        })

        call_count = self.mock_publish.call_count
        alarm_control_panel.alarm_arm_home(self.hass, 'abcd')
        self.hass.block_till_done()
        self.assertEqual(call_count, self.mock_publish.call_count)

    def test_arm_away_publishes_mqtt(self):
        """Test publishing of MQTT messages while armed."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
            }
        })

        alarm_control_panel.alarm_arm_away(self.hass)
        self.hass.block_till_done()
        self.assertEqual(('alarm/command', 'ARM_AWAY', 0, False),
                         self.mock_publish.mock_calls[-1][1])

    def test_arm_away_not_publishes_mqtt_with_invalid_code(self):
        """Test not publishing of MQTT messages with invalid code."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
                'code': '1234'
            }
        })

        call_count = self.mock_publish.call_count
        alarm_control_panel.alarm_arm_away(self.hass, 'abcd')
        self.hass.block_till_done()
        self.assertEqual(call_count, self.mock_publish.call_count)

    def test_disarm_publishes_mqtt(self):
        """Test publishing of MQTT messages while disarmed."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
            }
        })

        alarm_control_panel.alarm_disarm(self.hass)
        self.hass.block_till_done()
        self.assertEqual(('alarm/command', 'DISARM', 0, False),
                         self.mock_publish.mock_calls[-1][1])

    def test_disarm_not_publishes_mqtt_with_invalid_code(self):
        """Test not publishing of MQTT messages with invalid code."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
                'code': '1234'
            }
        })

        call_count = self.mock_publish.call_count
        alarm_control_panel.alarm_disarm(self.hass, 'abcd')
        self.hass.block_till_done()
        self.assertEqual(call_count, self.mock_publish.call_count)
