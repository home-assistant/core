"""Test state helpers."""
import asyncio
from datetime import timedelta
from unittest.mock import patch

import pytest
import voluptuous as vol

import homeassistant.core as ha
import homeassistant.components as core_components
from homeassistant.const import SERVICE_TURN_ON, SERVICE_TURN_OFF
from homeassistant.util import dt as dt_util
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import state
from homeassistant.const import (
    STATE_OPEN, STATE_CLOSED, STATE_LOCKED, STATE_UNLOCKED, STATE_ON,
    STATE_OFF, STATE_HOME, STATE_NOT_HOME)
from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA, SERVICE_MEDIA_PLAY, SERVICE_MEDIA_PAUSE)
from homeassistant.components.sun import (
    STATE_ABOVE_HORIZON, STATE_BELOW_HORIZON)
from tests.common import async_mock_service


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
def test_get_changed_since(hass):
    """Test get_changed_since."""
    point1 = dt_util.utcnow()
    point2 = point1 + timedelta(seconds=5)
    point3 = point2 + timedelta(seconds=5)

    with patch('homeassistant.core.dt_util.utcnow', return_value=point1):
        hass.states.async_set('light.test', 'on')
        state1 = hass.states.get('light.test')

    with patch('homeassistant.core.dt_util.utcnow', return_value=point2):
        hass.states.async_set('light.test2', 'on')
        state2 = hass.states.get('light.test2')

    with patch('homeassistant.core.dt_util.utcnow', return_value=point3):
        hass.states.async_set('light.test3', 'on')
        state3 = hass.states.get('light.test3')

    assert state.get_changed_since(
        [state1, state2, state3], point2) == [state2, state3]


@asyncio.coroutine
def test_reproduce_with_no_entity(hass):
    """Test reproduce_state with no entity."""
    calls = async_mock_service(
        hass, 'light', SERVICE_TURN_ON, state='on')

    yield from state.async_reproduce_state(hass, ha.State('light.test', 'on'))
    yield from hass.async_block_till_done()

    assert len(calls) == 0
    assert hass.states.get('light.test') is None


@asyncio.coroutine
def test_reproduce_group(hass):
    """Test reproduce_state with group."""
    res = yield from core_components.async_setup(hass, {})
    assert res
    light_calls = async_mock_service(hass, 'light', SERVICE_TURN_ON)
    hass.states.async_set(
        'group.test', 'off', {'entity_id': ['light.test1', 'light.test2']})

    yield from state.async_reproduce_state(hass, ha.State('group.test', 'on'))
    yield from hass.async_block_till_done()

    assert len(light_calls) == 1
    last_call = light_calls[-1]
    assert last_call.domain == 'light'
    assert last_call.service == SERVICE_TURN_ON
    assert last_call.data.get('entity_id') == ['light.test1', 'light.test2']


@asyncio.coroutine
def test_reproduce_turn_on(hass):
    """Test reproduce_state with SERVICE_TURN_ON."""
    calls = async_mock_service(
        hass, 'light', SERVICE_TURN_ON, state='on')
    hass.states.async_set('light.test', 'off')

    yield from state.async_reproduce_state(hass, ha.State('light.test', 'on'))
    yield from hass.async_block_till_done()

    assert len(calls) > 0
    last_call = calls[-1]
    assert last_call.domain == 'light'
    assert last_call.service == SERVICE_TURN_ON
    assert last_call.data.get('entity_id') == ['light.test']


@asyncio.coroutine
def test_reproduce_turn_off(hass):
    """Test reproduce_state with SERVICE_TURN_OFF."""
    calls = async_mock_service(
        hass, 'light', SERVICE_TURN_OFF, state='off')
    hass.states.async_set('light.test', 'on')

    yield from state.async_reproduce_state(hass, ha.State('light.test', 'off'))
    yield from hass.async_block_till_done()

    assert len(calls) > 0
    last_call = calls[-1]
    assert last_call.domain == 'light'
    assert last_call.service == SERVICE_TURN_OFF
    assert last_call.data.get('entity_id') == ['light.test']


@asyncio.coroutine
def test_reproduce_state_attributes(hass):
    """Test reproduce_state with state attributes."""
    schema = vol.Schema({
        'entity_id': cv.entity_ids, 'transition': 999, 'brightness': 100})
    calls = async_mock_service(hass, 'light', SERVICE_TURN_ON, schema, 'on')
    hass.states.async_set('light.test', 'off')

    state_attrs = {'transition': 999, 'brightness': 100}
    yield from state.async_reproduce_state(
        hass, ha.State('light.test', 'on', state_attrs))
    yield from hass.async_block_till_done()

    assert len(calls) > 0
    last_call = calls[-1]
    assert last_call.domain == 'light'
    assert last_call.service == SERVICE_TURN_ON
    assert last_call.data.get('transition') == 999
    assert last_call.data.get('brightness') == 100


@asyncio.coroutine
def test_reproduce_media_data(hass):
    """Test reproduce_state with SERVICE_PLAY_MEDIA."""
    schema = vol.Schema({
        'entity_id': cv.entity_ids,
        vol.Required('media_content_type'): str,
        vol.Required('media_content_id'): str})
    calls = async_mock_service(
        hass, 'media_player', SERVICE_PLAY_MEDIA, schema)
    hass.states.async_set('media_player.test', 'off')

    media_attributes = {
        'media_content_type': 'movie', 'media_content_id': 'batman'}
    yield from state.async_reproduce_state(
        hass, ha.State('media_player.test', 'None', media_attributes))
    yield from hass.async_block_till_done()

    assert len(calls) > 0
    last_call = calls[-1]
    assert last_call.domain == 'media_player'
    assert last_call.service == SERVICE_PLAY_MEDIA
    assert last_call.data.get('media_content_type') == 'movie'
    assert last_call.data.get('media_content_id') == 'batman'


@asyncio.coroutine
def test_reproduce_media_play(hass):
    """Test reproduce_state with SERVICE_MEDIA_PLAY."""
    calls = async_mock_service(
        hass, 'media_player', SERVICE_MEDIA_PLAY, state='playing')
    hass.states.async_set('media_player.test', 'off')

    yield from state.async_reproduce_state(
        hass, ha.State('media_player.test', 'playing'))
    yield from hass.async_block_till_done()

    assert len(calls) > 0
    last_call = calls[-1]
    assert last_call.domain == 'media_player'
    assert last_call.service == SERVICE_MEDIA_PLAY
    assert last_call.data.get('entity_id') == ['media_player.test']


@asyncio.coroutine
def test_reproduce_media_pause(hass):
    """Test reproduce_state with SERVICE_MEDIA_PAUSE."""
    calls = async_mock_service(
        hass, 'media_player', SERVICE_MEDIA_PAUSE, state='paused')
    hass.states.async_set('media_player.test', 'playing')

    yield from state.async_reproduce_state(
        hass, ha.State('media_player.test', 'paused'))
    yield from hass.async_block_till_done()

    assert len(calls) > 0
    last_call = calls[-1]
    assert last_call.domain == 'media_player'
    assert last_call.service == SERVICE_MEDIA_PAUSE
    assert last_call.data.get('entity_id') == ['media_player.test']


@asyncio.coroutine
def test_reproduce_bad_state(hass):
    """Test reproduce_state with bad state."""
    calls = async_mock_service(hass, 'light', SERVICE_TURN_ON)
    hass.states.async_set('light.test', 'off')

    yield from state.async_reproduce_state(hass, ha.State('light.test', 'bad'))
    yield from hass.async_block_till_done()

    assert len(calls) == 0
    assert hass.states.get('light.test').state == 'off'


@asyncio.coroutine
def test_reproduce_entities_same(hass):
    """Test reproduce_state with two entities with same domain and data."""
    schema = vol.Schema({
        'entity_id': cv.entity_ids, 'transition': int, 'brightness': int})
    light_calls = async_mock_service(
        hass, 'light', SERVICE_TURN_ON, schema, 'on')
    hass.states.async_set('light.test1', 'off')
    hass.states.async_set('light.test2', 'off')

    yield from state.async_reproduce_state(hass, [
        ha.State('light.test1', 'on', {'brightness': 95}),
        ha.State('light.test2', 'on', {'brightness': 95})])
    yield from hass.async_block_till_done()

    assert len(light_calls) == 1
    last_call = light_calls[-1]
    assert last_call.domain == 'light'
    assert last_call.service == SERVICE_TURN_ON
    assert last_call.data.get('entity_id') == ['light.test1', 'light.test2']
    assert last_call.data.get('brightness') == 95


def test_as_number_states():
    """Test state_as_number with states."""
    zero_states = (STATE_OFF, STATE_CLOSED, STATE_UNLOCKED,
                   STATE_BELOW_HORIZON, STATE_NOT_HOME)
    one_states = (STATE_ON, STATE_OPEN, STATE_LOCKED, STATE_ABOVE_HORIZON,
                  STATE_HOME)
    for _state in zero_states:
        assert state.state_as_number(ha.State('domain.test', _state, {})) == 0
    for _state in one_states:
        assert state.state_as_number(ha.State('domain.test', _state, {})) == 1


def test_as_number_coercion():
    """Test state_as_number with number."""
    for _state in ('0', '0.0', 0, 0.0):
        assert state.state_as_number(
            ha.State('domain.test', _state, {})) == 0.0
    for _state in ('1', '1.0', 1, 1.0):
        assert state.state_as_number(
            ha.State('domain.test', _state, {})) == 1.0


def test_as_number_invalid_cases():
    """Test state_as_number with invalid cases."""
    for _state in ('', 'foo', 'foo.bar', None, False, True, object, object()):
        with pytest.raises(ValueError):
            state.state_as_number(ha.State('domain.test', _state, {}))
