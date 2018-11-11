"""The tests for the manual Alarm Control Panel component."""
from datetime import timedelta
import unittest
from unittest.mock import patch, MagicMock
from homeassistant.components.alarm_control_panel import demo
from homeassistant.setup import setup_component, async_setup_component
from homeassistant.const import (
    STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_NIGHT, STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED)
from homeassistant.components import alarm_control_panel
import homeassistant.util.dt as dt_util
from tests.common import (fire_time_changed, get_test_home_assistant,
                          mock_component, mock_restore_cache)
from tests.components.alarm_control_panel import common
from homeassistant.core import State, CoreState

CODE = 'HELLO_CODE'


class TestAlarmControlPanelManual(unittest.TestCase):
    """Test the manual alarm module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_demo_platform(self):
        """Test setup."""
        mock = MagicMock()
        add_entities = mock.MagicMock()
        demo.setup_platform(self.hass, {}, add_entities)
        assert add_entities.call_count == 1

    def test_arm_home_no_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'pending_time': 0,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_home(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_HOME == \
            self.hass.states.get(entity_id).state

    def test_arm_home_with_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'pending_time': 1,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_home(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == \
            self.hass.states.get(entity_id).state

        state = self.hass.states.get(entity_id)
        assert state.attributes['post_pending_state'] == STATE_ALARM_ARMED_HOME

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_ARMED_HOME

    def test_arm_home_with_invalid_code(self):
        """Attempt to arm home without a valid code."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'pending_time': 1,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_home(self.hass, CODE + '2')
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

    def test_arm_away_no_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'pending_time': 0,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == \
            self.hass.states.get(entity_id).state

    def test_arm_home_with_template_code(self):
        """Attempt to arm with a template-based code."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code_template': '{{ "abc" }}',
                'pending_time': 0,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        self.hass.start()
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_home(self.hass, 'abc')
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_ARMED_HOME == state.state

    def test_arm_away_with_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'pending_time': 1,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == \
            self.hass.states.get(entity_id).state

        state = self.hass.states.get(entity_id)
        assert state.attributes['post_pending_state'] == STATE_ALARM_ARMED_AWAY

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_ARMED_AWAY

    def test_arm_away_with_invalid_code(self):
        """Attempt to arm away without a valid code."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'pending_time': 1,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE + '2')
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

    def test_arm_night_no_pending(self):
        """Test arm night method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'pending_time': 0,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_night(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_NIGHT == \
            self.hass.states.get(entity_id).state

    def test_arm_night_with_pending(self):
        """Test arm night method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'pending_time': 1,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_night(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == \
            self.hass.states.get(entity_id).state

        state = self.hass.states.get(entity_id)
        assert state.attributes['post_pending_state'] == \
            STATE_ALARM_ARMED_NIGHT

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_ARMED_NIGHT

        # Do not go to the pending state when updating to the same state
        common.alarm_arm_night(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_NIGHT == \
            self.hass.states.get(entity_id).state

    def test_arm_night_with_invalid_code(self):
        """Attempt to night home without a valid code."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'pending_time': 1,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_night(self.hass, CODE + '2')
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

    def test_trigger_no_pending(self):
        """Test triggering when no pending submitted method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'trigger_time': 1,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == \
            self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=60)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == \
            self.hass.states.get(entity_id).state

    def test_trigger_with_delay(self):
        """Test trigger method and switch from pending to triggered."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'delay_time': 1,
                'pending_time': 0,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_PENDING == state.state
        assert STATE_ALARM_TRIGGERED == \
            state.attributes['post_pending_state']

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_TRIGGERED == state.state

    def test_trigger_zero_trigger_time(self):
        """Test disabled trigger."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'pending_time': 0,
                'trigger_time': 0,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

    def test_trigger_zero_trigger_time_with_pending(self):
        """Test disabled trigger."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'pending_time': 2,
                'trigger_time': 0,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

    def test_trigger_with_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'pending_time': 2,
                'trigger_time': 3,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == \
            self.hass.states.get(entity_id).state

        state = self.hass.states.get(entity_id)
        assert state.attributes['post_pending_state'] == STATE_ALARM_TRIGGERED

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_TRIGGERED

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_DISARMED

    def test_trigger_with_unused_specific_delay(self):
        """Test trigger method and switch from pending to triggered."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'delay_time': 5,
                'pending_time': 0,
                'armed_home': {
                    'delay_time': 10
                },
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_PENDING == state.state
        assert STATE_ALARM_TRIGGERED == \
            state.attributes['post_pending_state']

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_TRIGGERED

    def test_trigger_with_specific_delay(self):
        """Test trigger method and switch from pending to triggered."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'delay_time': 10,
                'pending_time': 0,
                'armed_away': {
                    'delay_time': 1
                },
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_PENDING == state.state
        assert STATE_ALARM_TRIGGERED == \
            state.attributes['post_pending_state']

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_TRIGGERED

    def test_trigger_with_pending_and_delay(self):
        """Test trigger method and switch from pending to triggered."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'delay_time': 1,
                'pending_time': 0,
                'triggered': {
                    'pending_time': 1
                },
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_PENDING
        assert state.attributes['post_pending_state'] == STATE_ALARM_TRIGGERED

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_PENDING
        assert state.attributes['post_pending_state'] == STATE_ALARM_TRIGGERED

        future += timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_TRIGGERED

    def test_trigger_with_pending_and_specific_delay(self):
        """Test trigger method and switch from pending to triggered."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'delay_time': 10,
                'pending_time': 0,
                'armed_away': {
                    'delay_time': 1
                },
                'triggered': {
                    'pending_time': 1
                },
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_PENDING
        assert state.attributes['post_pending_state'] == STATE_ALARM_TRIGGERED

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_PENDING
        assert state.attributes['post_pending_state'] == STATE_ALARM_TRIGGERED

        future += timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_TRIGGERED

    def test_armed_home_with_specific_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'pending_time': 10,
                'armed_home': {
                    'pending_time': 2
                }
            }})

        entity_id = 'alarm_control_panel.test'

        common.alarm_arm_home(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == \
            self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_HOME == \
            self.hass.states.get(entity_id).state

    def test_armed_away_with_specific_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'pending_time': 10,
                'armed_away': {
                    'pending_time': 2
                }
            }})

        entity_id = 'alarm_control_panel.test'

        common.alarm_arm_away(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == \
            self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == \
            self.hass.states.get(entity_id).state

    def test_armed_night_with_specific_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'pending_time': 10,
                'armed_night': {
                    'pending_time': 2
                }
            }})

        entity_id = 'alarm_control_panel.test'

        common.alarm_arm_night(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == \
            self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_NIGHT == \
            self.hass.states.get(entity_id).state

    def test_trigger_with_specific_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'pending_time': 10,
                'triggered': {
                    'pending_time': 2
                },
                'trigger_time': 3,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        common.alarm_trigger(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == \
            self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == \
            self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

    def test_trigger_with_disarm_after_trigger(self):
        """Test disarm after trigger."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'trigger_time': 5,
                'pending_time': 0,
                'disarm_after_trigger': True
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == \
            self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

    def test_trigger_with_zero_specific_trigger_time(self):
        """Test trigger method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'trigger_time': 5,
                'disarmed': {
                    'trigger_time': 0
                },
                'pending_time': 0,
                'disarm_after_trigger': True
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

    def test_trigger_with_unused_zero_specific_trigger_time(self):
        """Test disarm after trigger."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'trigger_time': 5,
                'armed_home': {
                    'trigger_time': 0
                },
                'pending_time': 0,
                'disarm_after_trigger': True
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == \
            self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

    def test_trigger_with_specific_trigger_time(self):
        """Test disarm after trigger."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'disarmed': {
                    'trigger_time': 5
                },
                'pending_time': 0,
                'disarm_after_trigger': True
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == \
            self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

    def test_trigger_with_no_disarm_after_trigger(self):
        """Test disarm after trigger."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'trigger_time': 5,
                'pending_time': 0,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == \
            self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == \
            self.hass.states.get(entity_id).state

    def test_back_to_back_trigger_with_no_disarm_after_trigger(self):
        """Test disarm after trigger."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'trigger_time': 5,
                'pending_time': 0,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == \
            self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == \
            self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == \
            self.hass.states.get(entity_id).state

    def test_disarm_while_pending_trigger(self):
        """Test disarming while pending state."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'trigger_time': 5,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == \
            self.hass.states.get(entity_id).state

        common.alarm_disarm(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

    def test_disarm_during_trigger_with_invalid_code(self):
        """Test disarming while code is invalid."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'pending_time': 5,
                'code': CODE + '2',
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == \
            self.hass.states.get(entity_id).state

        common.alarm_disarm(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == \
            self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == \
            self.hass.states.get(entity_id).state

    def test_disarm_with_template_code(self):
        """Attempt to disarm with a valid or invalid template-based code."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code_template':
                    '{{ "" if from_state == "disarmed" else "abc" }}',
                'pending_time': 0,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        self.hass.start()
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_home(self.hass, 'def')
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_ARMED_HOME == state.state

        common.alarm_disarm(self.hass, 'def')
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_ARMED_HOME == state.state

        common.alarm_disarm(self.hass, 'abc')
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_DISARMED == state.state

    def test_arm_custom_bypass_no_pending(self):
        """Test arm custom bypass method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'pending_time': 0,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_custom_bypass(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_CUSTOM_BYPASS == \
            self.hass.states.get(entity_id).state

    def test_arm_custom_bypass_with_pending(self):
        """Test arm custom bypass method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'pending_time': 1,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_custom_bypass(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == \
            self.hass.states.get(entity_id).state

        state = self.hass.states.get(entity_id)
        assert state.attributes['post_pending_state'] == \
            STATE_ALARM_ARMED_CUSTOM_BYPASS

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_ARMED_CUSTOM_BYPASS

    def test_arm_custom_bypass_with_invalid_code(self):
        """Attempt to custom bypass without a valid code."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'pending_time': 1,
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_custom_bypass(self.hass, CODE + '2')
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

    def test_armed_custom_bypass_with_specific_pending(self):
        """Test arm custom bypass method."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'pending_time': 10,
                'armed_custom_bypass': {
                    'pending_time': 2
                }
            }})

        entity_id = 'alarm_control_panel.test'

        common.alarm_arm_custom_bypass(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == \
            self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_CUSTOM_BYPASS == \
            self.hass.states.get(entity_id).state

    def test_arm_away_after_disabled_disarmed(self):
        """Test pending state with and without zero trigger time."""
        assert setup_component(
            self.hass, alarm_control_panel.DOMAIN,
            {'alarm_control_panel': {
                'platform': 'manual',
                'name': 'test',
                'code': CODE,
                'pending_time': 0,
                'delay_time': 1,
                'armed_away': {
                    'pending_time': 1,
                },
                'disarmed': {
                    'trigger_time': 0
                },
                'disarm_after_trigger': False
            }})

        entity_id = 'alarm_control_panel.test'

        assert STATE_ALARM_DISARMED == \
            self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_PENDING == state.state
        assert STATE_ALARM_DISARMED == \
            state.attributes['pre_pending_state']
        assert STATE_ALARM_ARMED_AWAY == \
            state.attributes['post_pending_state']

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_PENDING == state.state
        assert STATE_ALARM_DISARMED == \
            state.attributes['pre_pending_state']
        assert STATE_ALARM_ARMED_AWAY == \
            state.attributes['post_pending_state']

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert STATE_ALARM_ARMED_AWAY == state.state

            common.alarm_trigger(self.hass, entity_id=entity_id)
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert STATE_ALARM_PENDING == state.state
            assert STATE_ALARM_ARMED_AWAY == \
                state.attributes['pre_pending_state']
            assert STATE_ALARM_TRIGGERED == \
                state.attributes['post_pending_state']

        future += timedelta(seconds=1)
        with patch(('homeassistant.components.alarm_control_panel.manual.'
                    'dt_util.utcnow'), return_value=future):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_TRIGGERED == state.state


async def test_restore_armed_state(hass):
    """Ensure armed state is restored on startup."""
    mock_restore_cache(hass, (
        State('alarm_control_panel.test', STATE_ALARM_ARMED_AWAY),
        ))

    hass.state = CoreState.starting
    mock_component(hass, 'recorder')

    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        'alarm_control_panel': {
            'platform': 'manual',
            'name': 'test',
            'pending_time': 0,
            'trigger_time': 0,
            'disarm_after_trigger': False
        }})

    state = hass.states.get('alarm_control_panel.test')
    assert state
    assert state.state == STATE_ALARM_ARMED_AWAY


async def test_restore_disarmed_state(hass):
    """Ensure disarmed state is restored on startup."""
    mock_restore_cache(hass, (
        State('alarm_control_panel.test', STATE_ALARM_DISARMED),
        ))

    hass.state = CoreState.starting
    mock_component(hass, 'recorder')

    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, {
        'alarm_control_panel': {
            'platform': 'manual',
            'name': 'test',
            'pending_time': 0,
            'trigger_time': 0,
            'disarm_after_trigger': False
        }})

    state = hass.states.get('alarm_control_panel.test')
    assert state
    assert state.state == STATE_ALARM_DISARMED
