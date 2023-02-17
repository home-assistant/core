"""The tests for weather recorder."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.db_schema import StateAttributes, States
from homeassistant.components.recorder.util import session_scope
from homeassistant.components.weather import ATTR_FORECAST, DOMAIN
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test weather attributes to be excluded."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {"platform": "demo"}})
    hass.config.units = METRIC_SYSTEM
    await hass.async_block_till_done()

    state = hass.states.get("weather.demo_weather_south")
    assert state.attributes[ATTR_FORECAST]

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
        assert ATTR_FORECAST not in state.attributes
