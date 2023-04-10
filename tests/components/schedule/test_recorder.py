"""The tests for recorder platform."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.db_schema import StateAttributes, States
from homeassistant.components.recorder.util import session_scope
from homeassistant.components.schedule.const import ATTR_NEXT_EVENT, DOMAIN
from homeassistant.const import ATTR_EDITABLE, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """Test attributes to be excluded."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test": {
                    "name": "Party mode",
                    "icon": "mdi:party-popper",
                    "monday": [{"from": "1:00", "to": "2:00"}],
                    "tuesday": [{"from": "2:00", "to": "3:00"}],
                    "wednesday": [{"from": "3:00", "to": "4:00"}],
                    "thursday": [{"from": "5:00", "to": "6:00"}],
                    "friday": [{"from": "7:00", "to": "8:00"}],
                    "saturday": [{"from": "9:00", "to": "10:00"}],
                    "sunday": [{"from": "11:00", "to": "12:00"}],
                }
            }
        },
    )

    state = hass.states.get("schedule.test")
    assert state
    assert state.attributes[ATTR_EDITABLE] is False
    assert state.attributes[ATTR_FRIENDLY_NAME]
    assert state.attributes[ATTR_ICON]
    assert state.attributes[ATTR_NEXT_EVENT]

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
    assert len(states) == 1
    assert ATTR_EDITABLE not in states[0].attributes
    assert ATTR_FRIENDLY_NAME in states[0].attributes
    assert ATTR_ICON in states[0].attributes
    assert ATTR_NEXT_EVENT not in states[0].attributes
