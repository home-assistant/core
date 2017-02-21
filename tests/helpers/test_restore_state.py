"""The tests for the Restore component."""
import asyncio
from unittest.mock import patch, MagicMock

from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import CoreState, State
import homeassistant.util.dt as dt_util

from homeassistant.helpers.restore_state import (
    async_get_last_state, DATA_RESTORE_CACHE)


@asyncio.coroutine
def test_caching_data(hass):
    """Test that we cache data."""
    hass.config.components.add('recorder')
    hass.state = CoreState.starting

    states = [
        State('input_boolean.b0', 'on'),
        State('input_boolean.b1', 'on'),
        State('input_boolean.b2', 'on'),
    ]

    with patch('homeassistant.helpers.restore_state.last_recorder_run',
               return_value=MagicMock(end=dt_util.utcnow())), \
            patch('homeassistant.helpers.restore_state.get_states',
                  return_value=states):
        state = yield from async_get_last_state(hass, 'input_boolean.b1')

    assert DATA_RESTORE_CACHE in hass.data
    assert hass.data[DATA_RESTORE_CACHE] == {st.entity_id: st for st in states}

    assert state is not None
    assert state.entity_id == 'input_boolean.b1'
    assert state.state == 'on'

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    yield from hass.async_block_till_done()

    assert DATA_RESTORE_CACHE not in hass.data
