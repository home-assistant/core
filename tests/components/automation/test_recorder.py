"""The tests for automation recorder."""
from __future__ import annotations

import pytest

from homeassistant.components import automation
from homeassistant.components.automation import ATTR_LAST_TRIGGERED
from homeassistant.components.recorder.models import StateAttributes, States
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, ATTR_MODE
from homeassistant.core import State
from homeassistant.helpers.script import ATTR_CUR
from homeassistant.setup import async_setup_component

from tests.common import async_init_recorder_component, async_mock_service
from tests.components.recorder.common import async_wait_recording_done_without_instance


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_exclude_attributes(hass, calls):
    """Test automation registered attributes to be excluded."""
    await async_init_recorder_component(hass)
    await hass.async_block_till_done()
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )
    await hass.async_block_till_done()
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert ["hello.world"] == calls[0].data.get(ATTR_ENTITY_ID)
    await async_wait_recording_done_without_instance(hass)

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
        assert ATTR_LAST_TRIGGERED not in state.attributes
        assert ATTR_MODE not in state.attributes
        assert ATTR_CUR not in state.attributes
        assert ATTR_FRIENDLY_NAME in state.attributes
