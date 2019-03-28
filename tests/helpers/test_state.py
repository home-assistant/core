"""Test state helpers."""
import asyncio
from datetime import timedelta
import unittest
from unittest.mock import patch

import homeassistant.core as ha
from homeassistant.setup import async_setup_component
from homeassistant.const import (SERVICE_TURN_ON, SERVICE_TURN_OFF)
from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.util import dt as dt_util
from homeassistant.helpers import state
from homeassistant.const import (
    STATE_OPEN, STATE_CLOSED,
    STATE_LOCKED, STATE_UNLOCKED,
    STATE_ON, STATE_OFF,
    STATE_HOME, STATE_NOT_HOME)
from homeassistant.components.sun import (STATE_ABOVE_HORIZON,
                                          STATE_BELOW_HORIZON)

from tests.common import get_test_home_assistant, mock_service
import pytest


@asyncio.coroutine
def test_async_track_states(hass):
    """Test AsyncTrackStates context manager."""
    point1 = dt_util.utcnow()
    point2 = point1 + timedelta(seconds=5)
    point3 = point2 + timedelta(seconds=5)

    with patch('homeassistant.core.dt_util.utcnow') as mock_utcnow:
        mock_utcnow.return_value = point2

        with state.AsyncTrackStates(hass) as states:
            mock_utcnow.return_value = point1
            hass.states.async_set('light.test', 'on')

            mock_utcnow.return_value = point2
            hass.states.async_set('light.test2', 'on')
            state2 = hass.states.get('light.test2')

            mock_utcnow.return_value = point3
            hass.states.async_set('light.test3', 'on')
            state3 = hass.states.get('light.test3')

    assert [state2, state3] == \
        sorted(states, key=lambda state: state.entity_id)


@asyncio.coroutine
def test_call_to_component(hass):
    """Test calls to components state reproduction functions."""
    with patch(('homeassistant.components.media_player.'
                'async_reproduce_states')) as media_player_fun:
        media_player_fun.return_value = asyncio.Future()
        media_player_fun.return_value.set_result(None)

        with patch(('homeassistant.components.climate.'
                    'async_reproduce_states')) as climate_fun:
            climate_fun.return_value = asyncio.Future()
            climate_fun.return_value.set_result(None)

            state_media_player = ha.State('media_player.test', 'bad')
            state_climate = ha.State('climate.test', 'bad')
            context = "dummy_context"

            yield from state.async_reproduce_state(
                hass,
                [state_media_player, state_climate],
                blocking=True,
                context=context)

            media_player_fun.assert_called_once_with(
                hass,
                [state_media_player],
                context=context)

            climate_fun.assert_called_once_with(
                hass,
                [state_climate],
                context=context)


class TestStateHelpers(unittest.TestCase):
    """Test the Home Assistant event helpers."""

    def setUp(self):     # pylint: disable=invalid-name
        """Run when tests are started."""
        self.hass = get_test_home_assistant()
        run_coroutine_threadsafe(async_setup_component(
            self.hass, 'homeassistant', {}), self.hass.loop).result()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop when tests are finished."""
        self.hass.stop()

    def test_get_changed_since(self):
        """Test get_changed_since."""
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

        assert [state2, state3] == \
            state.get_changed_since([state1, state2, state3], point2)

    def test_reproduce_with_no_entity(self):
        """Test reproduce_state with no entity."""
        calls = mock_service(self.hass, 'light', SERVICE_TURN_ON)

        state.reproduce_state(self.hass, ha.State('light.test', 'on'))

        self.hass.block_till_done()

        assert len(calls) == 0
        assert self.hass.states.get('light.test') is None

    def test_reproduce_turn_on(self):
        """Test reproduce_state with SERVICE_TURN_ON."""
        calls = mock_service(self.hass, 'light', SERVICE_TURN_ON)

        self.hass.states.set('light.test', 'off')

        state.reproduce_state(self.hass, ha.State('light.test', 'on'))

        self.hass.block_till_done()

        assert len(calls) > 0
        last_call = calls[-1]
        assert 'light' == last_call.domain
        assert SERVICE_TURN_ON == last_call.service
        assert ['light.test'] == last_call.data.get('entity_id')

    def test_reproduce_turn_off(self):
        """Test reproduce_state with SERVICE_TURN_OFF."""
        calls = mock_service(self.hass, 'light', SERVICE_TURN_OFF)

        self.hass.states.set('light.test', 'on')

        state.reproduce_state(self.hass, ha.State('light.test', 'off'))

        self.hass.block_till_done()

        assert len(calls) > 0
        last_call = calls[-1]
        assert 'light' == last_call.domain
        assert SERVICE_TURN_OFF == last_call.service
        assert ['light.test'] == last_call.data.get('entity_id')

    def test_reproduce_complex_data(self):
        """Test reproduce_state with complex service data."""
        calls = mock_service(self.hass, 'light', SERVICE_TURN_ON)

        self.hass.states.set('light.test', 'off')

        complex_data = ['hello', {'11': '22'}]

        state.reproduce_state(self.hass, ha.State('light.test', 'on', {
            'complex': complex_data
        }))

        self.hass.block_till_done()

        assert len(calls) > 0
        last_call = calls[-1]
        assert 'light' == last_call.domain
        assert SERVICE_TURN_ON == last_call.service
        assert complex_data == last_call.data.get('complex')

    def test_reproduce_bad_state(self):
        """Test reproduce_state with bad state."""
        calls = mock_service(self.hass, 'light', SERVICE_TURN_ON)

        self.hass.states.set('light.test', 'off')

        state.reproduce_state(self.hass, ha.State('light.test', 'bad'))

        self.hass.block_till_done()

        assert len(calls) == 0
        assert 'off' == self.hass.states.get('light.test').state

    def test_as_number_states(self):
        """Test state_as_number with states."""
        zero_states = (STATE_OFF, STATE_CLOSED, STATE_UNLOCKED,
                       STATE_BELOW_HORIZON, STATE_NOT_HOME)
        one_states = (STATE_ON, STATE_OPEN, STATE_LOCKED, STATE_ABOVE_HORIZON,
                      STATE_HOME)
        for _state in zero_states:
            assert 0 == state.state_as_number(
                ha.State('domain.test', _state, {}))
        for _state in one_states:
            assert 1 == state.state_as_number(
                ha.State('domain.test', _state, {}))

    def test_as_number_coercion(self):
        """Test state_as_number with number."""
        for _state in ('0', '0.0', 0, 0.0):
            assert 0.0 == state.state_as_number(
                    ha.State('domain.test', _state, {}))
        for _state in ('1', '1.0', 1, 1.0):
            assert 1.0 == state.state_as_number(
                    ha.State('domain.test', _state, {}))

    def test_as_number_invalid_cases(self):
        """Test state_as_number with invalid cases."""
        for _state in ('', 'foo', 'foo.bar', None, False, True, object,
                       object()):
            with pytest.raises(ValueError):
                state.state_as_number(ha.State('domain.test', _state, {}))
