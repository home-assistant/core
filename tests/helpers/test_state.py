"""
tests.helpers.test_state
~~~~~~~~~~~~~~~~~~~~~~~~

Test state helpers.
"""
from datetime import timedelta
import unittest
from unittest.mock import patch

import homeassistant.core as ha
import homeassistant.components as core_components
from homeassistant.const import SERVICE_TURN_ON
from homeassistant.util import dt as dt_util
from homeassistant.helpers import state
from homeassistant.const import (
    STATE_OPEN, STATE_CLOSED,
    STATE_LOCKED, STATE_UNLOCKED,
    STATE_ON, STATE_OFF)
from homeassistant.components.sun import (STATE_ABOVE_HORIZON,
                                          STATE_BELOW_HORIZON)

from tests.common import get_test_home_assistant, mock_service


class TestStateHelpers(unittest.TestCase):
    """ Tests the Home Assistant event helpers. """

    def setUp(self):     # pylint: disable=invalid-name
        """ Things to be run when tests are started. """
        self.hass = get_test_home_assistant()
        core_components.setup(self.hass, {})

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_get_changed_since(self):
        point1 = dt_util.utcnow()
        point2 = point1 + timedelta(seconds=5)
        point3 = point2 + timedelta(seconds=5)

        with patch('homeassistant.core.dt_util.utcnow', return_value=point1):
            self.hass.states.set('light.test', 'on')
            state1 = self.hass.states.get('light.test')

        with patch('homeassistant.core.dt_util.utcnow', return_value=point2):
            self.hass.states.set('light.test2', 'on')
            state2 = self.hass.states.get('light.test2')

        with patch('homeassistant.core.dt_util.utcnow', return_value=point3):
            self.hass.states.set('light.test3', 'on')
            state3 = self.hass.states.get('light.test3')

        self.assertEqual(
            [state2, state3],
            state.get_changed_since([state1, state2, state3], point2))

    def test_track_states(self):
        point1 = dt_util.utcnow()
        point2 = point1 + timedelta(seconds=5)
        point3 = point2 + timedelta(seconds=5)

        with patch('homeassistant.core.dt_util.utcnow') as mock_utcnow:
            mock_utcnow.return_value = point2

            with state.TrackStates(self.hass) as states:
                mock_utcnow.return_value = point1
                self.hass.states.set('light.test', 'on')

                mock_utcnow.return_value = point2
                self.hass.states.set('light.test2', 'on')
                state2 = self.hass.states.get('light.test2')

                mock_utcnow.return_value = point3
                self.hass.states.set('light.test3', 'on')
                state3 = self.hass.states.get('light.test3')

        self.assertEqual(
            sorted([state2, state3], key=lambda state: state.entity_id),
            sorted(states, key=lambda state: state.entity_id))

    def test_reproduce_state_with_turn_on(self):
        calls = mock_service(self.hass, 'light', SERVICE_TURN_ON)

        self.hass.states.set('light.test', 'off')

        state.reproduce_state(self.hass, ha.State('light.test', 'on'))

        self.hass.pool.block_till_done()

        self.assertTrue(len(calls) > 0)
        last_call = calls[-1]
        self.assertEqual('light', last_call.domain)
        self.assertEqual(SERVICE_TURN_ON, last_call.service)
        self.assertEqual(['light.test'], last_call.data.get('entity_id'))

    def test_reproduce_state_with_complex_service_data(self):
        calls = mock_service(self.hass, 'light', SERVICE_TURN_ON)

        self.hass.states.set('light.test', 'off')

        complex_data = ['hello', {'11': '22'}]

        state.reproduce_state(self.hass, ha.State('light.test', 'on', {
            'complex': complex_data
        }))

        self.hass.pool.block_till_done()

        self.assertTrue(len(calls) > 0)
        last_call = calls[-1]
        self.assertEqual('light', last_call.domain)
        self.assertEqual(SERVICE_TURN_ON, last_call.service)
        self.assertEqual(complex_data, last_call.data.get('complex'))

    def test_reproduce_state_with_group(self):
        light_calls = mock_service(self.hass, 'light', SERVICE_TURN_ON)

        self.hass.states.set('group.test', 'off', {
            'entity_id': ['light.test1', 'light.test2']})

        state.reproduce_state(self.hass, ha.State('group.test', 'on'))

        self.hass.pool.block_till_done()

        self.assertEqual(1, len(light_calls))
        last_call = light_calls[-1]
        self.assertEqual('light', last_call.domain)
        self.assertEqual(SERVICE_TURN_ON, last_call.service)
        self.assertEqual(['light.test1', 'light.test2'],
                         last_call.data.get('entity_id'))

    def test_reproduce_state_group_states_with_same_domain_and_data(self):
        light_calls = mock_service(self.hass, 'light', SERVICE_TURN_ON)

        self.hass.states.set('light.test1', 'off')
        self.hass.states.set('light.test2', 'off')

        state.reproduce_state(self.hass, [
            ha.State('light.test1', 'on', {'brightness': 95}),
            ha.State('light.test2', 'on', {'brightness': 95})])

        self.hass.pool.block_till_done()

        self.assertEqual(1, len(light_calls))
        last_call = light_calls[-1]
        self.assertEqual('light', last_call.domain)
        self.assertEqual(SERVICE_TURN_ON, last_call.service)
        self.assertEqual(['light.test1', 'light.test2'],
                         last_call.data.get('entity_id'))
        self.assertEqual(95, last_call.data.get('brightness'))

    def test_as_number_states(self):
        zero_states = (STATE_OFF, STATE_CLOSED, STATE_UNLOCKED,
                       STATE_BELOW_HORIZON)
        one_states = (STATE_ON, STATE_OPEN, STATE_LOCKED, STATE_ABOVE_HORIZON)
        for _state in zero_states:
            self.assertEqual(0, state.state_as_number(
                ha.State('domain.test', _state, {})))
        for _state in one_states:
            self.assertEqual(1, state.state_as_number(
                ha.State('domain.test', _state, {})))

    def test_as_number_coercion(self):
        for _state in ('0', '0.0', 0, 0.0):
            self.assertEqual(
                0.0, state.state_as_number(
                    ha.State('domain.test', _state, {})))
        for _state in ('1', '1.0', 1, 1.0):
            self.assertEqual(
                1.0, state.state_as_number(
                    ha.State('domain.test', _state, {})))

    def test_as_number_invalid_cases(self):
        for _state in ('', 'foo', 'foo.bar', None, False, True, object,
                       object()):
            self.assertRaises(ValueError,
                              state.state_as_number,
                              ha.State('domain.test', _state, {}))
