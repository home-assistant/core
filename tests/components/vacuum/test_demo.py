"""The tests for the Demo vacuum platform."""
import unittest

from homeassistant.components import vacuum
from homeassistant.components.vacuum import (
    ATTR_BATTERY_LEVEL, ATTR_COMMAND, ATTR_ENTITY_ID, ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST, ATTR_PARAMS, ATTR_STATUS, DOMAIN,
    ENTITY_ID_ALL_VACUUMS,
    SERVICE_SEND_COMMAND, SERVICE_SET_FAN_SPEED,
    STATE_DOCKED, STATE_CLEANING, STATE_PAUSED, STATE_IDLE,
    STATE_RETURNING)
from homeassistant.components.vacuum.demo import (
    DEMO_VACUUM_BASIC, DEMO_VACUUM_COMPLETE, DEMO_VACUUM_MINIMAL,
    DEMO_VACUUM_MOST, DEMO_VACUUM_NONE, DEMO_VACUUM_STATE, FAN_SPEEDS)
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES, CONF_PLATFORM, STATE_OFF, STATE_ON)
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, mock_service
from tests.components.vacuum import common


ENTITY_VACUUM_BASIC = '{}.{}'.format(DOMAIN, DEMO_VACUUM_BASIC).lower()
ENTITY_VACUUM_COMPLETE = '{}.{}'.format(DOMAIN, DEMO_VACUUM_COMPLETE).lower()
ENTITY_VACUUM_MINIMAL = '{}.{}'.format(DOMAIN, DEMO_VACUUM_MINIMAL).lower()
ENTITY_VACUUM_MOST = '{}.{}'.format(DOMAIN, DEMO_VACUUM_MOST).lower()
ENTITY_VACUUM_NONE = '{}.{}'.format(DOMAIN, DEMO_VACUUM_NONE).lower()
ENTITY_VACUUM_STATE = '{}.{}'.format(DOMAIN, DEMO_VACUUM_STATE).lower()


class TestVacuumDemo(unittest.TestCase):
    """Test the Demo vacuum."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        assert setup_component(
            self.hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: 'demo'}})

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_supported_features(self):
        """Test vacuum supported features."""
        state = self.hass.states.get(ENTITY_VACUUM_COMPLETE)
        assert 2047 == state.attributes.get(ATTR_SUPPORTED_FEATURES)
        assert "Charging" == state.attributes.get(ATTR_STATUS)
        assert 100 == state.attributes.get(ATTR_BATTERY_LEVEL)
        assert "medium" == state.attributes.get(ATTR_FAN_SPEED)
        assert FAN_SPEEDS == \
            state.attributes.get(ATTR_FAN_SPEED_LIST)
        assert STATE_OFF == state.state

        state = self.hass.states.get(ENTITY_VACUUM_MOST)
        assert 219 == state.attributes.get(ATTR_SUPPORTED_FEATURES)
        assert "Charging" == state.attributes.get(ATTR_STATUS)
        assert 100 == state.attributes.get(ATTR_BATTERY_LEVEL)
        assert state.attributes.get(ATTR_FAN_SPEED) is None
        assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None
        assert STATE_OFF == state.state

        state = self.hass.states.get(ENTITY_VACUUM_BASIC)
        assert 195 == state.attributes.get(ATTR_SUPPORTED_FEATURES)
        assert "Charging" == state.attributes.get(ATTR_STATUS)
        assert 100 == state.attributes.get(ATTR_BATTERY_LEVEL)
        assert state.attributes.get(ATTR_FAN_SPEED) is None
        assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None
        assert STATE_OFF == state.state

        state = self.hass.states.get(ENTITY_VACUUM_MINIMAL)
        assert 3 == state.attributes.get(ATTR_SUPPORTED_FEATURES)
        assert state.attributes.get(ATTR_STATUS) is None
        assert state.attributes.get(ATTR_BATTERY_LEVEL) is None
        assert state.attributes.get(ATTR_FAN_SPEED) is None
        assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None
        assert STATE_OFF == state.state

        state = self.hass.states.get(ENTITY_VACUUM_NONE)
        assert 0 == state.attributes.get(ATTR_SUPPORTED_FEATURES)
        assert state.attributes.get(ATTR_STATUS) is None
        assert state.attributes.get(ATTR_BATTERY_LEVEL) is None
        assert state.attributes.get(ATTR_FAN_SPEED) is None
        assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None
        assert STATE_OFF == state.state

        state = self.hass.states.get(ENTITY_VACUUM_STATE)
        assert 13436 == state.attributes.get(ATTR_SUPPORTED_FEATURES)
        assert STATE_DOCKED == state.state
        assert 100 == state.attributes.get(ATTR_BATTERY_LEVEL)
        assert "medium" == state.attributes.get(ATTR_FAN_SPEED)
        assert FAN_SPEEDS == \
            state.attributes.get(ATTR_FAN_SPEED_LIST)

    def test_methods(self):
        """Test if methods call the services as expected."""
        self.hass.states.set(ENTITY_VACUUM_BASIC, STATE_ON)
        self.hass.block_till_done()
        assert vacuum.is_on(self.hass, ENTITY_VACUUM_BASIC)

        self.hass.states.set(ENTITY_VACUUM_BASIC, STATE_OFF)
        self.hass.block_till_done()
        assert not vacuum.is_on(self.hass, ENTITY_VACUUM_BASIC)

        self.hass.states.set(ENTITY_ID_ALL_VACUUMS, STATE_ON)
        self.hass.block_till_done()
        assert vacuum.is_on(self.hass)

        self.hass.states.set(ENTITY_ID_ALL_VACUUMS, STATE_OFF)
        self.hass.block_till_done()
        assert not vacuum.is_on(self.hass)

        common.turn_on(self.hass, ENTITY_VACUUM_COMPLETE)
        self.hass.block_till_done()
        assert vacuum.is_on(self.hass, ENTITY_VACUUM_COMPLETE)

        common.turn_off(self.hass, ENTITY_VACUUM_COMPLETE)
        self.hass.block_till_done()
        assert not vacuum.is_on(self.hass, ENTITY_VACUUM_COMPLETE)

        common.toggle(self.hass, ENTITY_VACUUM_COMPLETE)
        self.hass.block_till_done()
        assert vacuum.is_on(self.hass, ENTITY_VACUUM_COMPLETE)

        common.start_pause(self.hass, ENTITY_VACUUM_COMPLETE)
        self.hass.block_till_done()
        assert not vacuum.is_on(self.hass, ENTITY_VACUUM_COMPLETE)

        common.start_pause(self.hass, ENTITY_VACUUM_COMPLETE)
        self.hass.block_till_done()
        assert vacuum.is_on(self.hass, ENTITY_VACUUM_COMPLETE)

        common.stop(self.hass, ENTITY_VACUUM_COMPLETE)
        self.hass.block_till_done()
        assert not vacuum.is_on(self.hass, ENTITY_VACUUM_COMPLETE)

        state = self.hass.states.get(ENTITY_VACUUM_COMPLETE)
        assert state.attributes.get(ATTR_BATTERY_LEVEL) < 100
        assert "Charging" != state.attributes.get(ATTR_STATUS)

        common.locate(self.hass, ENTITY_VACUUM_COMPLETE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_COMPLETE)
        assert "I'm over here" in state.attributes.get(ATTR_STATUS)

        common.return_to_base(self.hass, ENTITY_VACUUM_COMPLETE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_COMPLETE)
        assert "Returning home" in state.attributes.get(ATTR_STATUS)

        common.set_fan_speed(self.hass, FAN_SPEEDS[-1],
                             entity_id=ENTITY_VACUUM_COMPLETE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_COMPLETE)
        assert FAN_SPEEDS[-1] == state.attributes.get(ATTR_FAN_SPEED)

        common.clean_spot(self.hass, entity_id=ENTITY_VACUUM_COMPLETE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_COMPLETE)
        assert "spot" in state.attributes.get(ATTR_STATUS)
        assert STATE_ON == state.state

        common.start(self.hass, ENTITY_VACUUM_STATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_STATE)
        assert STATE_CLEANING == state.state

        common.pause(self.hass, ENTITY_VACUUM_STATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_STATE)
        assert STATE_PAUSED == state.state

        common.stop(self.hass, ENTITY_VACUUM_STATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_STATE)
        assert STATE_IDLE == state.state

        state = self.hass.states.get(ENTITY_VACUUM_STATE)
        assert state.attributes.get(ATTR_BATTERY_LEVEL) < 100
        assert STATE_DOCKED != state.state

        common.return_to_base(self.hass, ENTITY_VACUUM_STATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_STATE)
        assert STATE_RETURNING == state.state

        common.set_fan_speed(self.hass, FAN_SPEEDS[-1],
                             entity_id=ENTITY_VACUUM_STATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_STATE)
        assert FAN_SPEEDS[-1] == state.attributes.get(ATTR_FAN_SPEED)

        common.clean_spot(self.hass, entity_id=ENTITY_VACUUM_STATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_STATE)
        assert STATE_CLEANING == state.state

    def test_unsupported_methods(self):
        """Test service calls for unsupported vacuums."""
        self.hass.states.set(ENTITY_VACUUM_NONE, STATE_ON)
        self.hass.block_till_done()
        assert vacuum.is_on(self.hass, ENTITY_VACUUM_NONE)

        common.turn_off(self.hass, ENTITY_VACUUM_NONE)
        self.hass.block_till_done()
        assert vacuum.is_on(self.hass, ENTITY_VACUUM_NONE)

        common.stop(self.hass, ENTITY_VACUUM_NONE)
        self.hass.block_till_done()
        assert vacuum.is_on(self.hass, ENTITY_VACUUM_NONE)

        self.hass.states.set(ENTITY_VACUUM_NONE, STATE_OFF)
        self.hass.block_till_done()
        assert not vacuum.is_on(self.hass, ENTITY_VACUUM_NONE)

        common.turn_on(self.hass, ENTITY_VACUUM_NONE)
        self.hass.block_till_done()
        assert not vacuum.is_on(self.hass, ENTITY_VACUUM_NONE)

        common.toggle(self.hass, ENTITY_VACUUM_NONE)
        self.hass.block_till_done()
        assert not vacuum.is_on(self.hass, ENTITY_VACUUM_NONE)

        # Non supported methods:
        common.start_pause(self.hass, ENTITY_VACUUM_NONE)
        self.hass.block_till_done()
        assert not vacuum.is_on(self.hass, ENTITY_VACUUM_NONE)

        common.locate(self.hass, ENTITY_VACUUM_NONE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_NONE)
        assert state.attributes.get(ATTR_STATUS) is None

        common.return_to_base(self.hass, ENTITY_VACUUM_NONE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_NONE)
        assert state.attributes.get(ATTR_STATUS) is None

        common.set_fan_speed(self.hass, FAN_SPEEDS[-1],
                             entity_id=ENTITY_VACUUM_NONE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_NONE)
        assert FAN_SPEEDS[-1] != \
            state.attributes.get(ATTR_FAN_SPEED)

        common.clean_spot(self.hass, entity_id=ENTITY_VACUUM_BASIC)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_BASIC)
        assert "spot" not in state.attributes.get(ATTR_STATUS)
        assert STATE_OFF == state.state

        # VacuumDevice should not support start and pause methods.
        self.hass.states.set(ENTITY_VACUUM_COMPLETE, STATE_ON)
        self.hass.block_till_done()
        assert vacuum.is_on(self.hass, ENTITY_VACUUM_COMPLETE)

        common.pause(self.hass, ENTITY_VACUUM_COMPLETE)
        self.hass.block_till_done()
        assert vacuum.is_on(self.hass, ENTITY_VACUUM_COMPLETE)

        self.hass.states.set(ENTITY_VACUUM_COMPLETE, STATE_OFF)
        self.hass.block_till_done()
        assert not vacuum.is_on(self.hass, ENTITY_VACUUM_COMPLETE)

        common.start(self.hass, ENTITY_VACUUM_COMPLETE)
        self.hass.block_till_done()
        assert not vacuum.is_on(self.hass, ENTITY_VACUUM_COMPLETE)

        # StateVacuumDevice does not support on/off
        common.turn_on(self.hass, entity_id=ENTITY_VACUUM_STATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_STATE)
        assert STATE_CLEANING != state.state

        common.turn_off(self.hass, entity_id=ENTITY_VACUUM_STATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_STATE)
        assert STATE_RETURNING != state.state

        common.toggle(self.hass, entity_id=ENTITY_VACUUM_STATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_VACUUM_STATE)
        assert STATE_CLEANING != state.state

    def test_services(self):
        """Test vacuum services."""
        # Test send_command
        send_command_calls = mock_service(
            self.hass, DOMAIN, SERVICE_SEND_COMMAND)

        params = {"rotate": 150, "speed": 20}
        common.send_command(
            self.hass, 'test_command', entity_id=ENTITY_VACUUM_BASIC,
            params=params)

        self.hass.block_till_done()
        assert 1 == len(send_command_calls)
        call = send_command_calls[-1]

        assert DOMAIN == call.domain
        assert SERVICE_SEND_COMMAND == call.service
        assert ENTITY_VACUUM_BASIC == call.data[ATTR_ENTITY_ID]
        assert 'test_command' == call.data[ATTR_COMMAND]
        assert params == call.data[ATTR_PARAMS]

        # Test set fan speed
        set_fan_speed_calls = mock_service(
            self.hass, DOMAIN, SERVICE_SET_FAN_SPEED)

        common.set_fan_speed(
            self.hass, FAN_SPEEDS[0], entity_id=ENTITY_VACUUM_COMPLETE)

        self.hass.block_till_done()
        assert 1 == len(set_fan_speed_calls)
        call = set_fan_speed_calls[-1]

        assert DOMAIN == call.domain
        assert SERVICE_SET_FAN_SPEED == call.service
        assert ENTITY_VACUUM_COMPLETE == call.data[ATTR_ENTITY_ID]
        assert FAN_SPEEDS[0] == call.data[ATTR_FAN_SPEED]

    def test_set_fan_speed(self):
        """Test vacuum service to set the fan speed."""
        group_vacuums = ','.join([ENTITY_VACUUM_BASIC,
                                  ENTITY_VACUUM_COMPLETE,
                                  ENTITY_VACUUM_STATE])
        old_state_basic = self.hass.states.get(ENTITY_VACUUM_BASIC)
        old_state_complete = self.hass.states.get(ENTITY_VACUUM_COMPLETE)
        old_state_state = self.hass.states.get(ENTITY_VACUUM_STATE)

        common.set_fan_speed(
            self.hass, FAN_SPEEDS[0], entity_id=group_vacuums)

        self.hass.block_till_done()
        new_state_basic = self.hass.states.get(ENTITY_VACUUM_BASIC)
        new_state_complete = self.hass.states.get(ENTITY_VACUUM_COMPLETE)
        new_state_state = self.hass.states.get(ENTITY_VACUUM_STATE)

        assert old_state_basic == new_state_basic
        assert ATTR_FAN_SPEED not in new_state_basic.attributes

        assert old_state_complete != new_state_complete
        assert FAN_SPEEDS[1] == \
            old_state_complete.attributes[ATTR_FAN_SPEED]
        assert FAN_SPEEDS[0] == \
            new_state_complete.attributes[ATTR_FAN_SPEED]

        assert old_state_state != new_state_state
        assert FAN_SPEEDS[1] == \
            old_state_state.attributes[ATTR_FAN_SPEED]
        assert FAN_SPEEDS[0] == \
            new_state_state.attributes[ATTR_FAN_SPEED]

    def test_send_command(self):
        """Test vacuum service to send a command."""
        group_vacuums = ','.join([ENTITY_VACUUM_BASIC,
                                  ENTITY_VACUUM_COMPLETE])
        old_state_basic = self.hass.states.get(ENTITY_VACUUM_BASIC)
        old_state_complete = self.hass.states.get(ENTITY_VACUUM_COMPLETE)

        common.send_command(
            self.hass, 'test_command', params={"p1": 3},
            entity_id=group_vacuums)

        self.hass.block_till_done()
        new_state_basic = self.hass.states.get(ENTITY_VACUUM_BASIC)
        new_state_complete = self.hass.states.get(ENTITY_VACUUM_COMPLETE)

        assert old_state_basic == new_state_basic
        assert old_state_complete != new_state_complete
        assert STATE_ON == new_state_complete.state
        assert "Executing test_command({'p1': 3})" == \
            new_state_complete.attributes[ATTR_STATUS]
