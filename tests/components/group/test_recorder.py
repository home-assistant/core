"""The tests for group recorder."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components import group
from homeassistant.components.group import ATTR_AUTO, ATTR_ENTITY_ID, ATTR_ORDER
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.db_schema import StateAttributes, States
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test number registered attributes to be excluded."""
    hass.states.async_set("light.bowl", STATE_ON)

    assert await async_setup_component(hass, "light", {})
    assert await async_setup_component(
        hass,
        group.DOMAIN,
        {
            group.DOMAIN: {
                "group_zero": {"entities": "light.Bowl", "icon": "mdi:work"},
                "group_one": {"entities": "light.Bowl", "icon": "mdi:work"},
                "group_two": {"entities": "light.Bowl", "icon": "mdi:work"},
            }
        },
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    def _fetch_states() -> list[State]:
        with session_scope(hass=hass) as session:
            native_states = []
            attr_ids = {}
            for db_state_attributes in session.query(StateAttributes):
                attr_ids[
                    db_state_attributes.attributes_id
                ] = db_state_attributes.to_native()
            for db_state, _ in session.query(States, StateAttributes).outerjoin(
                StateAttributes, States.attributes_id == StateAttributes.attributes_id
            ):
                state = db_state.to_native()
                state.attributes = attr_ids[db_state.attributes_id]
                native_states.append(state)
            return native_states

    states: list[State] = await hass.async_add_executor_job(_fetch_states)
    assert len(states) > 1
    for state in states:
        if state.domain == group.DOMAIN:
            assert ATTR_AUTO not in state.attributes
            assert ATTR_ENTITY_ID not in state.attributes
            assert ATTR_ORDER not in state.attributes
            assert ATTR_FRIENDLY_NAME in state.attributes
