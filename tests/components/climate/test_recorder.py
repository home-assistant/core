"""The tests for climate recorder."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components import climate
from homeassistant.components.climate import (
    ATTR_FAN_MODES,
    ATTR_HVAC_MODES,
    ATTR_MAX_HUMIDITY,
    ATTR_MAX_TEMP,
    ATTR_MIN_HUMIDITY,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODES,
    ATTR_SWING_MODES,
    ATTR_TARGET_TEMP_STEP,
)
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.db_schema import StateAttributes, States
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test climate registered attributes to be excluded."""
    await async_setup_component(
        hass, climate.DOMAIN, {climate.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    def _fetch_states() -> list[State]:
        with session_scope(hass=hass) as session:
            native_states = []
            for db_state, db_state_attributes in session.query(
                States, StateAttributes
            ).outerjoin(
                StateAttributes, States.attributes_id == StateAttributes.attributes_id
            ):
                state = db_state.to_native()
                state.attributes = db_state_attributes.to_native()
                native_states.append(state)
            return native_states

    states: list[State] = await hass.async_add_executor_job(_fetch_states)
    assert len(states) > 1
    for state in states:
        assert ATTR_PRESET_MODES not in state.attributes
        assert ATTR_HVAC_MODES not in state.attributes
        assert ATTR_FAN_MODES not in state.attributes
        assert ATTR_SWING_MODES not in state.attributes
        assert ATTR_MIN_TEMP not in state.attributes
        assert ATTR_MAX_TEMP not in state.attributes
        assert ATTR_MIN_HUMIDITY not in state.attributes
        assert ATTR_MAX_HUMIDITY not in state.attributes
        assert ATTR_TARGET_TEMP_STEP not in state.attributes
        assert ATTR_FRIENDLY_NAME in state.attributes
