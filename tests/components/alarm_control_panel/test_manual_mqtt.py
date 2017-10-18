"""The tests for the manual_mqtt Alarm Control Panel component."""
from datetime import timedelta
import unittest
from unittest.mock import patch

from homeassistant.setup import setup_component
from homeassistant.const import (
    STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_NIGHT, STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED)
from homeassistant.components import alarm_control_panel
import homeassistant.util.dt as dt_util

from tests.common import (
    fire_time_changed, get_test_home_assistant,
    mock_mqtt_component, fire_mqtt_message, assert_setup_component)

CODE = 'HELLO_CODE'


class TestAlarmControlPanelManualMqtt(unittest.TestCase):
    """Test the manual_mqtt alarm module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_fail_setup_without_state_topic(self):
        """Test for failing with no state topic."""
        with assert_setup_component(0) as config:
            assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
                alarm_control_panel.DOMAIN: {
                    'platform': 'mqtt_alarm',
                    'command_topic': 'alarm/command'
                }
            })
            assert not config[alarm_control_panel.DOMAIN]

    def test_fail_setup_without_command_topic(self):
        """Test failing with no command topic."""
        with assert_setup_component(0):
            assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
                alarm_control_panel.DOMAIN: {
                    'platform': 'mqtt_alarm',
                    'state_topic': 'alarm/state'
                }
            })

    def test_arm_home_no_pending(self):
        """Test arm home method."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'code': CODE,
                'pending_time': 0,
                'disarm_after_trigger': False,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_arm_home(self.hass, CODE)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_HOME,
                         self.hass.states.get(entity_id).state)

    def test_arm_home_with_pending(self):
        """Test arm home method."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'code': CODE,
                'pending_time': 1,
                'disarm_after_trigger': False,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_arm_home(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        self.assertTrue(
            self.hass.states.is_state_attr(entity_id,
                                           'post_pending_state',
                                           STATE_ALARM_ARMED_HOME))

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_HOME,
                         self.hass.states.get(entity_id).state)

    def test_arm_home_with_invalid_code(self):
        """Attempt to arm home without a valid code."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'code': CODE,
                'pending_time': 1,
                'disarm_after_trigger': False,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_arm_home(self.hass, CODE + '2')
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

    def test_arm_away_no_pending(self):
        """Test arm home method."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'code': CODE,
                'pending_time': 0,
                'disarm_after_trigger': False,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_arm_away(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_AWAY,
                         self.hass.states.get(entity_id).state)

    def test_arm_away_with_pending(self):
        """Test arm home method."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'code': CODE,
                'pending_time': 1,
                'disarm_after_trigger': False,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_arm_away(self.hass, CODE)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        self.assertTrue(
            self.hass.states.is_state_attr(entity_id,
                                           'post_pending_state',
                                           STATE_ALARM_ARMED_AWAY))

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_AWAY,
                         self.hass.states.get(entity_id).state)

    def test_arm_away_with_invalid_code(self):
        """Attempt to arm away without a valid code."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'code': CODE,
                'pending_time': 1,
                'disarm_after_trigger': False,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_arm_away(self.hass, CODE + '2')
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

    def test_arm_night_no_pending(self):
        """Test arm night method."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'code': CODE,
                'pending_time': 0,
                'disarm_after_trigger': False,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_arm_night(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_NIGHT,
                         self.hass.states.get(entity_id).state)

    def test_arm_night_with_pending(self):
        """Test arm night method."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'code': CODE,
                'pending_time': 1,
                'disarm_after_trigger': False,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_arm_night(self.hass, CODE)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        self.assertTrue(
            self.hass.states.is_state_attr(entity_id,
                                           'post_pending_state',
                                           STATE_ALARM_ARMED_NIGHT))

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_NIGHT,
                         self.hass.states.get(entity_id).state)

    def test_arm_night_with_invalid_code(self):
        """Attempt to arm night without a valid code."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'code': CODE,
                'pending_time': 1,
                'disarm_after_trigger': False,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_arm_night(self.hass, CODE + '2')
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

    def test_trigger_no_pending(self):
        """Test triggering when no pending submitted method."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'trigger_time': 1,
                'disarm_after_trigger': False,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        future = dt_util.utcnow() + timedelta(seconds=60)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_TRIGGERED,
                         self.hass.states.get(entity_id).state)

    def test_trigger_with_pending(self):
        """Test arm home method."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'pending_time': 2,
                'trigger_time': 3,
                'disarm_after_trigger': False,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_trigger(self.hass)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        self.assertTrue(
            self.hass.states.is_state_attr(entity_id,
                                           'post_pending_state',
                                           STATE_ALARM_TRIGGERED))

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_TRIGGERED,
                         self.hass.states.get(entity_id).state)

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

    def test_trigger_with_disarm_after_trigger(self):
        """Test disarm after trigger."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'trigger_time': 5,
                'pending_time': 0,
                'disarm_after_trigger': True,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_TRIGGERED,
                         self.hass.states.get(entity_id).state)

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

    def test_back_to_back_trigger_with_no_disarm_after_trigger(self):
        """Test no disarm after back to back trigger."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'trigger_time': 5,
                'pending_time': 0,
                'disarm_after_trigger': False,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_arm_away(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_AWAY,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_TRIGGERED,
                         self.hass.states.get(entity_id).state)

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_AWAY,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_TRIGGERED,
                         self.hass.states.get(entity_id).state)

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_AWAY,
                         self.hass.states.get(entity_id).state)

    def test_disarm_while_pending_trigger(self):
        """Test disarming while pending state."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'trigger_time': 5,
                'disarm_after_trigger': False,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_trigger(self.hass)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_disarm(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

    def test_disarm_during_trigger_with_invalid_code(self):
        """Test disarming while code is invalid."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'pending_time': 5,
                'code': CODE + '2',
                'disarm_after_trigger': False,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_trigger(self.hass)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_disarm(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_TRIGGERED,
                         self.hass.states.get(entity_id).state)

    def test_armed_home_with_specific_pending(self):
        """Test arm home method."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'pending_time': 10,
                'armed_home': {
                    'pending_time': 2
                },
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        alarm_control_panel.alarm_arm_home(self.hass)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_HOME,
                         self.hass.states.get(entity_id).state)

    def test_armed_away_with_specific_pending(self):
        """Test arm home method."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'pending_time': 10,
                'armed_away': {
                    'pending_time': 2
                },
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        alarm_control_panel.alarm_arm_away(self.hass)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_AWAY,
                         self.hass.states.get(entity_id).state)

    def test_armed_night_with_specific_pending(self):
        """Test arm home method."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'pending_time': 10,
                'armed_night': {
                    'pending_time': 2
                },
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        alarm_control_panel.alarm_arm_night(self.hass)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_NIGHT,
                         self.hass.states.get(entity_id).state)

    def test_trigger_with_specific_pending(self):
        """Test arm home method."""
        self.assertTrue(setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual_mqtt',
                'name': 'test',
                'pending_time': 10,
                'triggered': {
                    'pending_time': 2
                },
                'trigger_time': 3,
                'disarm_after_trigger': False,
                'command_topic': 'alarm/command',
                'state_topic': 'alarm/state',
            }}))

        entity_id = 'alarm_control_panel.test'

        alarm_control_panel.alarm_arm_home(self.hass)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        future = dt_util.utcnow() + timedelta(seconds=10)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_HOME,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_trigger(self.hass)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_TRIGGERED,
                         self.hass.states.get(entity_id).state)

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_HOME,
                         self.hass.states.get(entity_id).state)

    def test_arm_home_via_command_topic(self):
        """Test arming home via command topic."""
        assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'manual_mqtt',
                'name': 'test',
                'pending_time': 1,
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
                'payload_arm_home': 'ARM_HOME',
            }
        })

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        # Fire the arm command via MQTT; ensure state changes to pending
        fire_mqtt_message(self.hass, 'alarm/command', 'ARM_HOME')
        self.hass.block_till_done()
        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        # Fast-forward a little bit
        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_HOME,
                         self.hass.states.get(entity_id).state)

    def test_arm_away_via_command_topic(self):
        """Test arming away via command topic."""
        assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'manual_mqtt',
                'name': 'test',
                'pending_time': 1,
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
                'payload_arm_away': 'ARM_AWAY',
            }
        })

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        # Fire the arm command via MQTT; ensure state changes to pending
        fire_mqtt_message(self.hass, 'alarm/command', 'ARM_AWAY')
        self.hass.block_till_done()
        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        # Fast-forward a little bit
        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_AWAY,
                         self.hass.states.get(entity_id).state)

    def test_arm_night_via_command_topic(self):
        """Test arming night via command topic."""
        assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'manual_mqtt',
                'name': 'test',
                'pending_time': 1,
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
                'payload_arm_night': 'ARM_NIGHT',
            }
        })

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        # Fire the arm command via MQTT; ensure state changes to pending
        fire_mqtt_message(self.hass, 'alarm/command', 'ARM_NIGHT')
        self.hass.block_till_done()
        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        # Fast-forward a little bit
        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_ARMED_NIGHT,
                         self.hass.states.get(entity_id).state)

    def test_disarm_pending_via_command_topic(self):
        """Test disarming pending alarm via command topic."""
        assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'manual_mqtt',
                'name': 'test',
                'pending_time': 1,
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
                'payload_disarm': 'DISARM',
            }
        })

        entity_id = 'alarm_control_panel.test'

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

        alarm_control_panel.alarm_trigger(self.hass)
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_PENDING,
                         self.hass.states.get(entity_id).state)

        # Now that we're pending, receive a command to disarm
        fire_mqtt_message(self.hass, 'alarm/command', 'DISARM')
        self.hass.block_till_done()

        self.assertEqual(STATE_ALARM_DISARMED,
                         self.hass.states.get(entity_id).state)

    def test_state_changes_are_published_to_mqtt(self):
        """Test publishing of MQTT messages when state changes."""
        assert setup_component(self.hass, alarm_control_panel.DOMAIN, {
            alarm_control_panel.DOMAIN: {
                'platform': 'manual_mqtt',
                'name': 'test',
                'pending_time': 1,
                'trigger_time': 1,
                'state_topic': 'alarm/state',
                'command_topic': 'alarm/command',
            }
        })

        # Component should send disarmed alarm state on startup
        self.hass.block_till_done()
        self.assertEqual(('alarm/state', STATE_ALARM_DISARMED, 0, True),
                         self.mock_publish.mock_calls[-2][1])

        # Arm in home mode
        alarm_control_panel.alarm_arm_home(self.hass)
        self.hass.block_till_done()
        self.assertEqual(('alarm/state', STATE_ALARM_PENDING, 0, True),
                         self.mock_publish.mock_calls[-2][1])
        # Fast-forward a little bit
        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()
        self.assertEqual(('alarm/state', STATE_ALARM_ARMED_HOME, 0, True),
                         self.mock_publish.mock_calls[-2][1])

        # Arm in away mode
        alarm_control_panel.alarm_arm_away(self.hass)
        self.hass.block_till_done()
        self.assertEqual(('alarm/state', STATE_ALARM_PENDING, 0, True),
                         self.mock_publish.mock_calls[-2][1])
        # Fast-forward a little bit
        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()
        self.assertEqual(('alarm/state', STATE_ALARM_ARMED_AWAY, 0, True),
                         self.mock_publish.mock_calls[-2][1])

        # Arm in night mode
        alarm_control_panel.alarm_arm_night(self.hass)
        self.hass.block_till_done()
        self.assertEqual(('alarm/state', STATE_ALARM_PENDING, 0, True),
                         self.mock_publish.mock_calls[-2][1])
        # Fast-forward a little bit
        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual_mqtt.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()
        self.assertEqual(('alarm/state', STATE_ALARM_ARMED_NIGHT, 0, True),
                         self.mock_publish.mock_calls[-2][1])

        # Disarm
        alarm_control_panel.alarm_disarm(self.hass)
        self.hass.block_till_done()
        self.assertEqual(('alarm/state', STATE_ALARM_DISARMED, 0, True),
                         self.mock_publish.mock_calls[-2][1])
