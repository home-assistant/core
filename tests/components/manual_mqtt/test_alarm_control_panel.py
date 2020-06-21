"""The tests for the manual_mqtt Alarm Control Panel component."""
from datetime import timedelta
import unittest

from homeassistant.components import alarm_control_panel
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import Mock, patch
from tests.common import (
    assert_setup_component,
    fire_mqtt_message,
    fire_time_changed,
    get_test_home_assistant,
    mock_mqtt_component,
)
from tests.components.alarm_control_panel import common

CODE = "HELLO_CODE"


class TestAlarmControlPanelManualMqtt(unittest.TestCase):
    """Test the manual_mqtt alarm module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config_entries._async_schedule_save = Mock()
        self.mock_publish = mock_mqtt_component(self.hass)
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_fail_setup_without_state_topic(self):
        """Test for failing with no state topic."""
        with assert_setup_component(0) as config:
            assert setup_component(
                self.hass,
                alarm_control_panel.DOMAIN,
                {
                    alarm_control_panel.DOMAIN: {
                        "platform": "mqtt_alarm",
                        "command_topic": "alarm/command",
                    }
                },
            )
            assert not config[alarm_control_panel.DOMAIN]

    def test_fail_setup_without_command_topic(self):
        """Test failing with no command topic."""
        with assert_setup_component(0):
            assert setup_component(
                self.hass,
                alarm_control_panel.DOMAIN,
                {
                    alarm_control_panel.DOMAIN: {
                        "platform": "mqtt_alarm",
                        "state_topic": "alarm/state",
                    }
                },
            )

    def test_arm_home_no_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "pending_time": 0,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_home(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_HOME == self.hass.states.get(entity_id).state

    def test_arm_home_no_pending_when_code_not_req(self):
        """Test arm home method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "code_arm_required": False,
                    "pending_time": 0,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_home(self.hass, 0)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_HOME == self.hass.states.get(entity_id).state

    def test_arm_home_with_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "pending_time": 1,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_home(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        state = self.hass.states.get(entity_id)
        assert state.attributes["post_pending_state"] == STATE_ALARM_ARMED_HOME

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_HOME == self.hass.states.get(entity_id).state

    def test_arm_home_with_invalid_code(self):
        """Attempt to arm home without a valid code."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "pending_time": 1,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_home(self.hass, f"{CODE}2")
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

    def test_arm_away_no_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "pending_time": 0,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == self.hass.states.get(entity_id).state

    def test_arm_away_no_pending_when_code_not_req(self):
        """Test arm home method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code_arm_required": False,
                    "code": CODE,
                    "pending_time": 0,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, 0, entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == self.hass.states.get(entity_id).state

    def test_arm_home_with_template_code(self):
        """Attempt to arm with a template-based code."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code_template": '{{ "abc" }}',
                    "pending_time": 0,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_home(self.hass, "abc")
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_ARMED_HOME == state.state

    def test_arm_away_with_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "pending_time": 1,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        state = self.hass.states.get(entity_id)
        assert state.attributes["post_pending_state"] == STATE_ALARM_ARMED_AWAY

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == self.hass.states.get(entity_id).state

    def test_arm_away_with_invalid_code(self):
        """Attempt to arm away without a valid code."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "pending_time": 1,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, f"{CODE}2")
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

    def test_arm_night_no_pending(self):
        """Test arm night method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "pending_time": 0,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_night(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_NIGHT == self.hass.states.get(entity_id).state

    def test_arm_night_no_pending_when_code_not_req(self):
        """Test arm night method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code_arm_required": False,
                    "code": CODE,
                    "pending_time": 0,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_night(self.hass, 0, entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_NIGHT == self.hass.states.get(entity_id).state

    def test_arm_night_with_pending(self):
        """Test arm night method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "pending_time": 1,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_night(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        state = self.hass.states.get(entity_id)
        assert state.attributes["post_pending_state"] == STATE_ALARM_ARMED_NIGHT

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_NIGHT == self.hass.states.get(entity_id).state

        # Do not go to the pending state when updating to the same state
        common.alarm_arm_night(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_NIGHT == self.hass.states.get(entity_id).state

    def test_arm_night_with_invalid_code(self):
        """Attempt to arm night without a valid code."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "pending_time": 1,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_night(self.hass, f"{CODE}2")
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

    def test_trigger_no_pending(self):
        """Test triggering when no pending submitted method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "trigger_time": 1,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=60)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == self.hass.states.get(entity_id).state

    def test_trigger_with_delay(self):
        """Test trigger method and switch from pending to triggered."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "delay_time": 1,
                    "pending_time": 0,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_PENDING == state.state
        assert STATE_ALARM_TRIGGERED == state.attributes["post_pending_state"]

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_TRIGGERED == state.state

    def test_trigger_zero_trigger_time(self):
        """Test disabled trigger."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "pending_time": 0,
                    "trigger_time": 0,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

    def test_trigger_zero_trigger_time_with_pending(self):
        """Test disabled trigger."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "pending_time": 2,
                    "trigger_time": 0,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

    def test_trigger_with_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "pending_time": 2,
                    "trigger_time": 3,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        state = self.hass.states.get(entity_id)
        assert state.attributes["post_pending_state"] == STATE_ALARM_TRIGGERED

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

    def test_trigger_with_disarm_after_trigger(self):
        """Test disarm after trigger."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "trigger_time": 5,
                    "pending_time": 0,
                    "disarm_after_trigger": True,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

    def test_trigger_with_zero_specific_trigger_time(self):
        """Test trigger method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "trigger_time": 5,
                    "disarmed": {"trigger_time": 0},
                    "pending_time": 0,
                    "disarm_after_trigger": True,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

    def test_trigger_with_unused_zero_specific_trigger_time(self):
        """Test disarm after trigger."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "trigger_time": 5,
                    "armed_home": {"trigger_time": 0},
                    "pending_time": 0,
                    "disarm_after_trigger": True,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

    def test_trigger_with_specific_trigger_time(self):
        """Test disarm after trigger."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "disarmed": {"trigger_time": 5},
                    "pending_time": 0,
                    "disarm_after_trigger": True,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

    def test_back_to_back_trigger_with_no_disarm_after_trigger(self):
        """Test no disarm after back to back trigger."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "trigger_time": 5,
                    "pending_time": 0,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE, entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == self.hass.states.get(entity_id).state

    def test_disarm_while_pending_trigger(self):
        """Test disarming while pending state."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "trigger_time": 5,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        common.alarm_disarm(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

    def test_disarm_during_trigger_with_invalid_code(self):
        """Test disarming while code is invalid."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "pending_time": 5,
                    "code": f"{CODE}2",
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        common.alarm_disarm(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == self.hass.states.get(entity_id).state

    def test_trigger_with_unused_specific_delay(self):
        """Test trigger method and switch from pending to triggered."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "delay_time": 5,
                    "pending_time": 0,
                    "armed_home": {"delay_time": 10},
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_PENDING == state.state
        assert STATE_ALARM_TRIGGERED == state.attributes["post_pending_state"]

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_TRIGGERED

    def test_trigger_with_specific_delay(self):
        """Test trigger method and switch from pending to triggered."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "delay_time": 10,
                    "pending_time": 0,
                    "armed_away": {"delay_time": 1},
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_PENDING == state.state
        assert STATE_ALARM_TRIGGERED == state.attributes["post_pending_state"]

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_TRIGGERED

    def test_trigger_with_pending_and_delay(self):
        """Test trigger method and switch from pending to triggered."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "delay_time": 1,
                    "pending_time": 0,
                    "triggered": {"pending_time": 1},
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_PENDING
        assert state.attributes["post_pending_state"] == STATE_ALARM_TRIGGERED

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_PENDING
        assert state.attributes["post_pending_state"] == STATE_ALARM_TRIGGERED

        future += timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_TRIGGERED

    def test_trigger_with_pending_and_specific_delay(self):
        """Test trigger method and switch from pending to triggered."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "delay_time": 10,
                    "pending_time": 0,
                    "armed_away": {"delay_time": 1},
                    "triggered": {"pending_time": 1},
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE)
        self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_PENDING
        assert state.attributes["post_pending_state"] == STATE_ALARM_TRIGGERED

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_PENDING
        assert state.attributes["post_pending_state"] == STATE_ALARM_TRIGGERED

        future += timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert state.state == STATE_ALARM_TRIGGERED

    def test_armed_home_with_specific_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "pending_time": 10,
                    "armed_home": {"pending_time": 2},
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        common.alarm_arm_home(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_HOME == self.hass.states.get(entity_id).state

    def test_armed_away_with_specific_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "pending_time": 10,
                    "armed_away": {"pending_time": 2},
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        common.alarm_arm_away(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == self.hass.states.get(entity_id).state

    def test_armed_night_with_specific_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "pending_time": 10,
                    "armed_night": {"pending_time": 2},
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        common.alarm_arm_night(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_NIGHT == self.hass.states.get(entity_id).state

    def test_trigger_with_specific_pending(self):
        """Test arm home method."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "pending_time": 10,
                    "triggered": {"pending_time": 2},
                    "trigger_time": 3,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        common.alarm_trigger(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=2)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_TRIGGERED == self.hass.states.get(entity_id).state

        future = dt_util.utcnow() + timedelta(seconds=5)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

    def test_arm_away_after_disabled_disarmed(self):
        """Test pending state with and without zero trigger time."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code": CODE,
                    "pending_time": 0,
                    "delay_time": 1,
                    "armed_away": {"pending_time": 1},
                    "disarmed": {"trigger_time": 0},
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_away(self.hass, CODE)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_PENDING == state.state
        assert STATE_ALARM_DISARMED == state.attributes["pre_pending_state"]
        assert STATE_ALARM_ARMED_AWAY == state.attributes["post_pending_state"]

        common.alarm_trigger(self.hass, entity_id=entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_PENDING == state.state
        assert STATE_ALARM_DISARMED == state.attributes["pre_pending_state"]
        assert STATE_ALARM_ARMED_AWAY == state.attributes["post_pending_state"]

        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert STATE_ALARM_ARMED_AWAY == state.state

            common.alarm_trigger(self.hass, entity_id=entity_id)
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert STATE_ALARM_PENDING == state.state
            assert STATE_ALARM_ARMED_AWAY == state.attributes["pre_pending_state"]
            assert STATE_ALARM_TRIGGERED == state.attributes["post_pending_state"]

        future += timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_TRIGGERED == state.state

    def test_disarm_with_template_code(self):
        """Attempt to disarm with a valid or invalid template-based code."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                "alarm_control_panel": {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "code_template": '{{ "" if from_state == "disarmed" else "abc" }}',
                    "pending_time": 0,
                    "disarm_after_trigger": False,
                    "command_topic": "alarm/command",
                    "state_topic": "alarm/state",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_arm_home(self.hass, "def")
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_ARMED_HOME == state.state

        common.alarm_disarm(self.hass, "def")
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_ARMED_HOME == state.state

        common.alarm_disarm(self.hass, "abc")
        self.hass.block_till_done()

        state = self.hass.states.get(entity_id)
        assert STATE_ALARM_DISARMED == state.state

    def test_arm_home_via_command_topic(self):
        """Test arming home via command topic."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                alarm_control_panel.DOMAIN: {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "pending_time": 1,
                    "state_topic": "alarm/state",
                    "command_topic": "alarm/command",
                    "payload_arm_home": "ARM_HOME",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        # Fire the arm command via MQTT; ensure state changes to pending
        fire_mqtt_message(self.hass, "alarm/command", "ARM_HOME")
        self.hass.block_till_done()
        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        # Fast-forward a little bit
        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_HOME == self.hass.states.get(entity_id).state

    def test_arm_away_via_command_topic(self):
        """Test arming away via command topic."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                alarm_control_panel.DOMAIN: {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "pending_time": 1,
                    "state_topic": "alarm/state",
                    "command_topic": "alarm/command",
                    "payload_arm_away": "ARM_AWAY",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        # Fire the arm command via MQTT; ensure state changes to pending
        fire_mqtt_message(self.hass, "alarm/command", "ARM_AWAY")
        self.hass.block_till_done()
        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        # Fast-forward a little bit
        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_AWAY == self.hass.states.get(entity_id).state

    def test_arm_night_via_command_topic(self):
        """Test arming night via command topic."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                alarm_control_panel.DOMAIN: {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "pending_time": 1,
                    "state_topic": "alarm/state",
                    "command_topic": "alarm/command",
                    "payload_arm_night": "ARM_NIGHT",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        # Fire the arm command via MQTT; ensure state changes to pending
        fire_mqtt_message(self.hass, "alarm/command", "ARM_NIGHT")
        self.hass.block_till_done()
        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        # Fast-forward a little bit
        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        assert STATE_ALARM_ARMED_NIGHT == self.hass.states.get(entity_id).state

    def test_disarm_pending_via_command_topic(self):
        """Test disarming pending alarm via command topic."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                alarm_control_panel.DOMAIN: {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "pending_time": 1,
                    "state_topic": "alarm/state",
                    "command_topic": "alarm/command",
                    "payload_disarm": "DISARM",
                }
            },
        )
        self.hass.block_till_done()

        entity_id = "alarm_control_panel.test"

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

        common.alarm_trigger(self.hass)
        self.hass.block_till_done()

        assert STATE_ALARM_PENDING == self.hass.states.get(entity_id).state

        # Now that we're pending, receive a command to disarm
        fire_mqtt_message(self.hass, "alarm/command", "DISARM")
        self.hass.block_till_done()

        assert STATE_ALARM_DISARMED == self.hass.states.get(entity_id).state

    def test_state_changes_are_published_to_mqtt(self):
        """Test publishing of MQTT messages when state changes."""
        assert setup_component(
            self.hass,
            alarm_control_panel.DOMAIN,
            {
                alarm_control_panel.DOMAIN: {
                    "platform": "manual_mqtt",
                    "name": "test",
                    "pending_time": 1,
                    "trigger_time": 1,
                    "state_topic": "alarm/state",
                    "command_topic": "alarm/command",
                }
            },
        )
        self.hass.block_till_done()

        # Component should send disarmed alarm state on startup
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            "alarm/state", STATE_ALARM_DISARMED, 0, True
        )
        self.mock_publish.async_publish.reset_mock()

        # Arm in home mode
        common.alarm_arm_home(self.hass)
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            "alarm/state", STATE_ALARM_PENDING, 0, True
        )
        self.mock_publish.async_publish.reset_mock()
        # Fast-forward a little bit
        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            "alarm/state", STATE_ALARM_ARMED_HOME, 0, True
        )
        self.mock_publish.async_publish.reset_mock()

        # Arm in away mode
        common.alarm_arm_away(self.hass)
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            "alarm/state", STATE_ALARM_PENDING, 0, True
        )
        self.mock_publish.async_publish.reset_mock()
        # Fast-forward a little bit
        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            "alarm/state", STATE_ALARM_ARMED_AWAY, 0, True
        )
        self.mock_publish.async_publish.reset_mock()

        # Arm in night mode
        common.alarm_arm_night(self.hass)
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            "alarm/state", STATE_ALARM_PENDING, 0, True
        )
        self.mock_publish.async_publish.reset_mock()
        # Fast-forward a little bit
        future = dt_util.utcnow() + timedelta(seconds=1)
        with patch(
            (
                "homeassistant.components.manual_mqtt.alarm_control_panel."
                "dt_util.utcnow"
            ),
            return_value=future,
        ):
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            "alarm/state", STATE_ALARM_ARMED_NIGHT, 0, True
        )
        self.mock_publish.async_publish.reset_mock()

        # Disarm
        common.alarm_disarm(self.hass)
        self.hass.block_till_done()
        self.mock_publish.async_publish.assert_called_once_with(
            "alarm/state", STATE_ALARM_DISARMED, 0, True
        )
