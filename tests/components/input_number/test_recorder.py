"""The tests for recorder platform."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.input_number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_MODE,
    ATTR_STEP,
    DOMAIN,
)
from homeassistant.components.recorder.db_schema import StateAttributes, States
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import ATTR_EDITABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(
    hass: HomeAssistant, recorder_mock, enable_custom_integrations: None
):
    """Test attributes to be excluded."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"test": {"min": 0, "max": 100}}}
    )

    state = hass.states.get("input_number.test")
    assert state
    assert state.attributes[ATTR_EDITABLE] is False
    assert state.attributes[ATTR_MIN] == 0
    assert state.attributes[ATTR_MAX] == 100
    assert state.attributes[ATTR_STEP] == 1
    assert state.attributes[ATTR_MODE] == "slider"

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
    assert len(states) == 1
    assert ATTR_EDITABLE not in states[0].attributes
    assert ATTR_MIN not in states[0].attributes
    assert ATTR_MAX not in states[0].attributes
    assert ATTR_STEP not in states[0].attributes
    assert ATTR_MODE not in states[0].attributes
