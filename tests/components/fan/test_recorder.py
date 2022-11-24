"""The tests for fan recorder."""
from __future__ import annotations

from datetime import timedelta

from spencerassistant.components import fan
from spencerassistant.components.fan import ATTR_PRESET_MODES
from spencerassistant.components.recorder.db_schema import StateAttributes, States
from spencerassistant.components.recorder.util import session_scope
from spencerassistant.const import ATTR_FRIENDLY_NAME
from spencerassistant.core import State
from spencerassistant.setup import async_setup_component
from spencerassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(recorder_mock, hass):
    """Test fan registered attributes to be excluded."""
    await async_setup_component(hass, fan.DOMAIN, {fan.DOMAIN: {"platform": "demo"}})
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    def _fetch_states() -> list[State]:
        with session_scope(hass=hass) as session:
            native_states = []
            for db_state, db_state_attributes in session.query(States, StateAttributes):
                state = db_state.to_native()
                state.attributes = db_state_attributes.to_native()
                native_states.append(state)
            return native_states

    states: list[State] = await hass.async_add_executor_job(_fetch_states)
    assert len(states) > 1
    for state in states:
        assert ATTR_PRESET_MODES not in state.attributes
        assert ATTR_FRIENDLY_NAME in state.attributes
