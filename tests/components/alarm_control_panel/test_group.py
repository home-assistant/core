"""The tests for the manual Alarm Control Panel component."""
from datetime import timedelta
import unittest
from unittest.mock import patch

from homeassistant.setup import setup_component
from homeassistant.const import (
    ATTR_PRE_PENDING_STATE, ATTR_POST_PENDING_STATE,
    STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_NIGHT, STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED)
import homeassistant.components.alarm_control_panel as alarm

import homeassistant.util.dt as dt_util

from tests.common import (
    assert_setup_component, fire_time_changed, get_test_home_assistant)

CODE = '1234'
TAMPER_CODE = '123456'
TAMPER_CODE_TEMPLATE = '{{"1234" if from_state != "triggered" else "123456"}}'


class TestAlarmControlPanelGroup(unittest.TestCase):
    """Test the group alarm module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        with assert_setup_component(5):
            setup_component(self.hass, alarm.DOMAIN, {
                'alarm_control_panel': [{
                    # The living room doesn't do anything special
                    'platform': 'manual',
                    'name': 'livingroom',
                    'code': CODE,
                    'delay_time': 0,
                    'pending_time': 0,
                    'disarmed': {
                        'trigger_time': 0
                    }
                }, {
                    # The garage gives you some time to come and go,
                    # when armed "away"
                    'platform': 'manual',
                    'name': 'garage',
                    'code': CODE,
                    'delay_time': 30,
                    'pending_time': 30,
                    'armed_home': {
                        'delay_time': 0,
                        'pending_time': 0
                    },
                    'armed_night': {
                        'delay_time': 0,
                        'pending_time': 0
                    },
                    'triggered': {
                        'pending_time': 0
                    },
                    'disarmed': {
                        'trigger_time': 0
                    }
                }, {
                    # The bedroom is turned off at night
                    'platform': 'manual',
                    'name': 'bedroom',
                    'code': CODE,
                    'delay_time': 0,
                    'pending_time': 0,
                    'armed_night': {
                        'trigger_time': 0
                    },
                    'disarmed': {
                        'trigger_time': 0
                    }
                }, {
                    # The tampering switch is turned off by a special code,
                    # and triggers the siren even if the alarm is not armed
                    'platform': 'manual',
                    'name': 'tamper',
                    'delay_time': 0,
                    'pending_time': 0,
                    'code_template': TAMPER_CODE_TEMPLATE,
                }, {
                    'platform': 'group',
                    'name': 'testgroup',
                    'panels': [
                        {'panel': 'alarm_control_panel.livingroom'},
                        {'panel': 'alarm_control_panel.garage'},
                        {'panel': 'alarm_control_panel.bedroom'},
                        {'panel': 'alarm_control_panel.tamper'},
                    ]
                }]
            })

        self.hass.start()
        self.hass.block_till_done()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def _assert_states(self, **states):
        for which, state in states.items():
            entity_id = 'alarm_control_panel.' + which
            self.assertEqual(state, self.hass.states.get(entity_id).state,
                             msg=('mismatch on %s state' % which))

    def test_create(self):
        """Basic test for state method."""
        self._assert_states(testgroup=STATE_ALARM_DISARMED)

    def test_group_arm(self):
        """Test propagation of the children panel's states."""
        self._assert_states(testgroup=STATE_ALARM_DISARMED)
        alarm.alarm_arm_home(self.hass, CODE,
                             entity_id='alarm_control_panel.testgroup')
        self.hass.block_till_done()
        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()
            self._assert_states(garage=STATE_ALARM_ARMED_HOME,
                                livingroom=STATE_ALARM_ARMED_HOME,
                                bedroom=STATE_ALARM_ARMED_HOME,
                                tamper=STATE_ALARM_ARMED_HOME,
                                testgroup=STATE_ALARM_ARMED_HOME)

    def test_child_trigger_no_action(self):
        """Test triggering a child with zero trigger time."""
        self._assert_states(testgroup=STATE_ALARM_DISARMED)
        alarm.alarm_trigger(self.hass,
                            entity_id='alarm_control_panel.livingroom')
        self.hass.block_till_done()
        self._assert_states(testgroup=STATE_ALARM_DISARMED)

    def test_child_trigger_and_disarm(self):
        """Test triggering a child with non-zero trigger time."""
        entity_id = 'alarm_control_panel.testgroup'
        self._assert_states(testgroup=STATE_ALARM_DISARMED)
        alarm.alarm_trigger(self.hass, entity_id='alarm_control_panel.tamper')
        self.hass.block_till_done()
        self._assert_states(garage=STATE_ALARM_DISARMED,
                            livingroom=STATE_ALARM_DISARMED,
                            bedroom=STATE_ALARM_DISARMED,
                            tamper=STATE_ALARM_TRIGGERED,
                            testgroup=STATE_ALARM_TRIGGERED)

        alarm.alarm_disarm(self.hass, CODE, entity_id)
        self.hass.block_till_done()
        self._assert_states(tamper=STATE_ALARM_TRIGGERED,
                            testgroup=STATE_ALARM_TRIGGERED)

        alarm.alarm_disarm(self.hass, TAMPER_CODE, entity_id)
        self.hass.block_till_done()
        self._assert_states(testgroup=STATE_ALARM_DISARMED)

    def test_child_arm_separately(self):
        """Test arming a child of a group."""
        entity_id = 'alarm_control_panel.testgroup'
        self._assert_states(testgroup=STATE_ALARM_DISARMED)
        alarm.alarm_arm_away(self.hass, CODE,
                             entity_id='alarm_control_panel.bedroom')
        self.hass.block_till_done()

        self._assert_states(garage=STATE_ALARM_DISARMED,
                            livingroom=STATE_ALARM_DISARMED,
                            bedroom=STATE_ALARM_ARMED_AWAY,
                            tamper=STATE_ALARM_DISARMED,
                            testgroup=STATE_ALARM_ARMED_CUSTOM_BYPASS)
        alarm.alarm_disarm(self.hass, CODE, entity_id=entity_id)
        self.hass.block_till_done()
        self._assert_states(testgroup=STATE_ALARM_DISARMED)

    def test_child_arm_separately_pending(self):
        """Test arming a child of a group with non-zero pending_time."""
        entity_id = 'alarm_control_panel.testgroup'
        self._assert_states(testgroup=STATE_ALARM_DISARMED)
        alarm.alarm_arm_away(self.hass, CODE,
                             entity_id='alarm_control_panel.garage')
        self.hass.block_till_done()

        self._assert_states(garage=STATE_ALARM_PENDING,
                            livingroom=STATE_ALARM_DISARMED,
                            bedroom=STATE_ALARM_DISARMED,
                            tamper=STATE_ALARM_DISARMED,
                            testgroup=STATE_ALARM_PENDING)

        state = self.hass.states.get('alarm_control_panel.garage')
        self.assertEqual(STATE_ALARM_DISARMED,
                         state.attributes[ATTR_PRE_PENDING_STATE])
        self.assertEqual(STATE_ALARM_ARMED_AWAY,
                         state.attributes[ATTR_POST_PENDING_STATE])
        state = self.hass.states.get(entity_id)
        self.assertEqual(STATE_ALARM_DISARMED,
                         state.attributes[ATTR_PRE_PENDING_STATE])
        self.assertEqual(STATE_ALARM_ARMED_CUSTOM_BYPASS,
                         state.attributes[ATTR_POST_PENDING_STATE])
        alarm.alarm_disarm(self.hass, CODE, entity_id=entity_id)
        self.hass.block_till_done()
        self._assert_states(testgroup=STATE_ALARM_DISARMED)

    def test_arm_invalid_code(self):
        """Test arming with an invalid code."""
        entity_id = 'alarm_control_panel.testgroup'
        self._assert_states(garage=STATE_ALARM_DISARMED,
                            bedroom=STATE_ALARM_DISARMED,
                            livingroom=STATE_ALARM_DISARMED,
                            tamper=STATE_ALARM_DISARMED,
                            testgroup=STATE_ALARM_DISARMED)
        alarm.alarm_arm_night(self.hass, 'abc', entity_id=entity_id)
        self.hass.block_till_done()
        self._assert_states(garage=STATE_ALARM_DISARMED,
                            bedroom=STATE_ALARM_DISARMED,
                            livingroom=STATE_ALARM_DISARMED,
                            tamper=STATE_ALARM_DISARMED,
                            testgroup=STATE_ALARM_DISARMED)

    def test_arm_invalid_code_for_template(self):
        """Test arming with an invalid code for the disarmed state."""
        entity_id = 'alarm_control_panel.testgroup'
        self._assert_states(garage=STATE_ALARM_DISARMED,
                            bedroom=STATE_ALARM_DISARMED,
                            livingroom=STATE_ALARM_DISARMED,
                            tamper=STATE_ALARM_DISARMED,
                            testgroup=STATE_ALARM_DISARMED)
        alarm.alarm_arm_night(self.hass, TAMPER_CODE, entity_id=entity_id)
        self.hass.block_till_done()
        self._assert_states(garage=STATE_ALARM_DISARMED,
                            bedroom=STATE_ALARM_DISARMED,
                            livingroom=STATE_ALARM_DISARMED,
                            tamper=STATE_ALARM_DISARMED,
                            testgroup=STATE_ALARM_DISARMED)

    def test_arm_and_trigger_ignored_zone(self):
        """Test armed group with a child that has zero trigger-time."""
        entity_id = 'alarm_control_panel.testgroup'
        self._assert_states(testgroup=STATE_ALARM_DISARMED)
        alarm.alarm_arm_night(self.hass, CODE, entity_id=entity_id)
        self.hass.block_till_done()
        self._assert_states(testgroup=STATE_ALARM_ARMED_NIGHT,
                            garage=STATE_ALARM_ARMED_NIGHT,
                            livingroom=STATE_ALARM_ARMED_NIGHT,
                            bedroom=STATE_ALARM_ARMED_NIGHT,
                            tamper=STATE_ALARM_ARMED_NIGHT)
        alarm.alarm_trigger(self.hass, entity_id='alarm_control_panel.bedroom')
        self.hass.block_till_done()
        self._assert_states(testgroup=STATE_ALARM_ARMED_NIGHT,
                            garage=STATE_ALARM_ARMED_NIGHT,
                            livingroom=STATE_ALARM_ARMED_NIGHT,
                            bedroom=STATE_ALARM_ARMED_NIGHT,
                            tamper=STATE_ALARM_ARMED_NIGHT)
        alarm.alarm_disarm(self.hass, CODE, entity_id=entity_id)
        self.hass.block_till_done()
        self._assert_states(testgroup=STATE_ALARM_DISARMED)

    def test_arm_with_child_pending(self):
        """Test 'pending' state during pending_time."""
        entity_id = 'alarm_control_panel.testgroup'
        self._assert_states(testgroup=STATE_ALARM_DISARMED)
        alarm.alarm_arm_away(self.hass, CODE, entity_id=entity_id)
        self.hass.block_till_done()

        self._assert_states(testgroup=STATE_ALARM_PENDING,
                            garage=STATE_ALARM_PENDING,
                            livingroom=STATE_ALARM_ARMED_AWAY,
                            bedroom=STATE_ALARM_ARMED_AWAY,
                            tamper=STATE_ALARM_ARMED_AWAY)
        state = self.hass.states.get('alarm_control_panel.garage')
        self.assertEqual(STATE_ALARM_DISARMED,
                         state.attributes[ATTR_PRE_PENDING_STATE])
        self.assertEqual(STATE_ALARM_ARMED_AWAY,
                         state.attributes[ATTR_POST_PENDING_STATE])

        # pre-state is custom bypass because the garage is still disarmed
        state = self.hass.states.get(entity_id)
        self.assertEqual(STATE_ALARM_ARMED_CUSTOM_BYPASS,
                         state.attributes[ATTR_PRE_PENDING_STATE])
        self.assertEqual(STATE_ALARM_ARMED_AWAY,
                         state.attributes[ATTR_POST_PENDING_STATE])

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

            alarm.alarm_trigger(self.hass,
                                entity_id='alarm_control_panel.garage')
            self.hass.block_till_done()
            state = self.hass.states.get('alarm_control_panel.garage')
            self.assertEqual(STATE_ALARM_DISARMED,
                             state.attributes[ATTR_PRE_PENDING_STATE])
            self.assertEqual(STATE_ALARM_ARMED_AWAY,
                             state.attributes[ATTR_POST_PENDING_STATE])
            state = self.hass.states.get(entity_id)
            self.assertEqual(STATE_ALARM_PENDING, state.state)
            self.assertEqual(STATE_ALARM_ARMED_CUSTOM_BYPASS,
                             state.attributes[ATTR_PRE_PENDING_STATE])
            self.assertEqual(STATE_ALARM_ARMED_AWAY,
                             state.attributes[ATTR_POST_PENDING_STATE])

            alarm.alarm_trigger(self.hass,
                                entity_id='alarm_control_panel.livingroom')
            self.hass.block_till_done()
            self._assert_states(testgroup=STATE_ALARM_TRIGGERED,
                                garage=STATE_ALARM_PENDING,
                                livingroom=STATE_ALARM_TRIGGERED,
                                bedroom=STATE_ALARM_ARMED_AWAY,
                                tamper=STATE_ALARM_ARMED_AWAY)

        alarm.alarm_disarm(self.hass, CODE, entity_id=entity_id)
        self.hass.block_till_done()
        self._assert_states(testgroup=STATE_ALARM_DISARMED,
                            garage=STATE_ALARM_DISARMED,
                            livingroom=STATE_ALARM_DISARMED,
                            bedroom=STATE_ALARM_DISARMED,
                            tamper=STATE_ALARM_DISARMED)

    def test_trigger_with_child_delay(self):
        """Test 'pending' state during delay_time."""
        entity_id = 'alarm_control_panel.testgroup'
        self._assert_states(testgroup=STATE_ALARM_DISARMED)
        alarm.alarm_arm_away(self.hass, CODE, entity_id=entity_id)
        self.hass.block_till_done()

        self._assert_states(testgroup=STATE_ALARM_PENDING,
                            garage=STATE_ALARM_PENDING,
                            livingroom=STATE_ALARM_ARMED_AWAY,
                            bedroom=STATE_ALARM_ARMED_AWAY,
                            tamper=STATE_ALARM_ARMED_AWAY)

        state = self.hass.states.get(entity_id)
        self.assertEqual(STATE_ALARM_ARMED_CUSTOM_BYPASS,
                         state.attributes[ATTR_PRE_PENDING_STATE])
        self.assertEqual(STATE_ALARM_ARMED_AWAY,
                         state.attributes[ATTR_POST_PENDING_STATE])

        future = dt_util.utcnow() + timedelta(seconds=31)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

            self._assert_states(testgroup=STATE_ALARM_ARMED_AWAY,
                                garage=STATE_ALARM_ARMED_AWAY,
                                livingroom=STATE_ALARM_ARMED_AWAY,
                                bedroom=STATE_ALARM_ARMED_AWAY,
                                tamper=STATE_ALARM_ARMED_AWAY)

            alarm.alarm_trigger(self.hass,
                                entity_id='alarm_control_panel.garage')
            self.hass.block_till_done()
            self._assert_states(testgroup=STATE_ALARM_PENDING,
                                garage=STATE_ALARM_PENDING,
                                livingroom=STATE_ALARM_ARMED_AWAY,
                                bedroom=STATE_ALARM_ARMED_AWAY,
                                tamper=STATE_ALARM_ARMED_AWAY)

            state = self.hass.states.get(entity_id)
            self.assertEqual(STATE_ALARM_ARMED_AWAY,
                             state.attributes[ATTR_PRE_PENDING_STATE])
            self.assertEqual(STATE_ALARM_TRIGGERED,
                             state.attributes[ATTR_POST_PENDING_STATE])

            state = self.hass.states.get('alarm_control_panel.garage')
            self.assertEqual(STATE_ALARM_ARMED_AWAY,
                             state.attributes[ATTR_PRE_PENDING_STATE])
            self.assertEqual(STATE_ALARM_TRIGGERED,
                             state.attributes[ATTR_POST_PENDING_STATE])

        future = dt_util.utcnow() + timedelta(seconds=62)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

            self._assert_states(testgroup=STATE_ALARM_TRIGGERED,
                                garage=STATE_ALARM_TRIGGERED,
                                livingroom=STATE_ALARM_ARMED_AWAY,
                                bedroom=STATE_ALARM_ARMED_AWAY,
                                tamper=STATE_ALARM_ARMED_AWAY)

        alarm.alarm_disarm(self.hass, CODE, entity_id=entity_id)
        self.hass.block_till_done()
        self._assert_states(testgroup=STATE_ALARM_DISARMED)

    def test_trigger_and_disarm_with_child_delay(self):
        """Test 'pending' state causing the group to trigger."""
        entity_id = 'alarm_control_panel.testgroup'
        self._assert_states(testgroup=STATE_ALARM_DISARMED)
        alarm.alarm_arm_away(self.hass, CODE, entity_id=entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        self.assertEqual(STATE_ALARM_PENDING, state.state)
        self.assertEqual(STATE_ALARM_ARMED_CUSTOM_BYPASS,
                         state.attributes[ATTR_PRE_PENDING_STATE])
        self.assertEqual(STATE_ALARM_ARMED_AWAY,
                         state.attributes[ATTR_POST_PENDING_STATE])

        future = dt_util.utcnow() + timedelta(seconds=31)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

            self._assert_states(testgroup=STATE_ALARM_ARMED_AWAY,
                                garage=STATE_ALARM_ARMED_AWAY,
                                livingroom=STATE_ALARM_ARMED_AWAY,
                                bedroom=STATE_ALARM_ARMED_AWAY,
                                tamper=STATE_ALARM_ARMED_AWAY)

            alarm.alarm_trigger(self.hass,
                                entity_id='alarm_control_panel.garage')
            self.hass.block_till_done()
            self._assert_states(testgroup=STATE_ALARM_PENDING,
                                garage=STATE_ALARM_PENDING,
                                livingroom=STATE_ALARM_ARMED_AWAY,
                                bedroom=STATE_ALARM_ARMED_AWAY,
                                tamper=STATE_ALARM_ARMED_AWAY)

            state = self.hass.states.get(entity_id)
            self.assertEqual(STATE_ALARM_ARMED_AWAY,
                             state.attributes[ATTR_PRE_PENDING_STATE])
            self.assertEqual(STATE_ALARM_TRIGGERED,
                             state.attributes[ATTR_POST_PENDING_STATE])

            state = self.hass.states.get('alarm_control_panel.garage')
            self.assertEqual(STATE_ALARM_ARMED_AWAY,
                             state.attributes[ATTR_PRE_PENDING_STATE])
            self.assertEqual(STATE_ALARM_TRIGGERED,
                             state.attributes[ATTR_POST_PENDING_STATE])

        future = dt_util.utcnow() + timedelta(seconds=42)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

            self._assert_states(testgroup=STATE_ALARM_PENDING,
                                garage=STATE_ALARM_PENDING,
                                livingroom=STATE_ALARM_ARMED_AWAY,
                                bedroom=STATE_ALARM_ARMED_AWAY,
                                tamper=STATE_ALARM_ARMED_AWAY)

            alarm.alarm_disarm(self.hass, CODE, entity_id=entity_id)
            self.hass.block_till_done()
            self._assert_states(testgroup=STATE_ALARM_DISARMED)
