"""The tests for update recorder."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.recorder.db_schema import StateAttributes, States
from homeassistant.components.recorder.util import session_scope
from homeassistant.components.update.const import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_RELEASE_SUMMARY,
    DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_PICTURE, CONF_PLATFORM
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(
    hass: HomeAssistant, recorder_mock, enable_custom_integrations: None
):
    """Test update attributes to be excluded."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()
    state = hass.states.get("update.update_already_in_progress")
    assert state.attributes[ATTR_IN_PROGRESS] == 50
    assert (
        state.attributes[ATTR_ENTITY_PICTURE]
        == "https://brands.home-assistant.io/_/test/icon.png"
    )
    await async_setup_component(hass, DOMAIN, {})

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
        assert ATTR_ENTITY_PICTURE not in state.attributes
        assert ATTR_IN_PROGRESS not in state.attributes
        assert ATTR_RELEASE_SUMMARY not in state.attributes
        assert ATTR_INSTALLED_VERSION in state.attributes
