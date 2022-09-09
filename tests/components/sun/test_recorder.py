"""The tests for sun recorder."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.recorder.db_schema import StateAttributes, States
from homeassistant.components.recorder.util import session_scope
from homeassistant.components.sun import (
    DOMAIN,
    STATE_ATTR_AZIMUTH,
    STATE_ATTR_ELEVATION,
    STATE_ATTR_NEXT_DAWN,
    STATE_ATTR_NEXT_DUSK,
    STATE_ATTR_NEXT_MIDNIGHT,
    STATE_ATTR_NEXT_NOON,
    STATE_ATTR_NEXT_RISING,
    STATE_ATTR_NEXT_SETTING,
    STATE_ATTR_RISING,
)
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import State
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(hass, recorder_mock):
    """Test sun attributes to be excluded."""
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    def _fetch_sun_states() -> list[State]:
        with session_scope(hass=hass) as session:
            native_states = []
            for db_state, db_state_attributes in session.query(States, StateAttributes):
                state = db_state.to_native()
                state.attributes = db_state_attributes.to_native()
                native_states.append(state)
            return native_states

    states: list[State] = await hass.async_add_executor_job(_fetch_sun_states)
    assert len(states) > 1
    for state in states:
        assert STATE_ATTR_AZIMUTH not in state.attributes
        assert STATE_ATTR_ELEVATION not in state.attributes
        assert STATE_ATTR_NEXT_DAWN not in state.attributes
        assert STATE_ATTR_NEXT_DUSK not in state.attributes
        assert STATE_ATTR_NEXT_MIDNIGHT not in state.attributes
        assert STATE_ATTR_NEXT_NOON not in state.attributes
        assert STATE_ATTR_NEXT_RISING not in state.attributes
        assert STATE_ATTR_NEXT_SETTING not in state.attributes
        assert STATE_ATTR_RISING not in state.attributes
        assert ATTR_FRIENDLY_NAME in state.attributes
