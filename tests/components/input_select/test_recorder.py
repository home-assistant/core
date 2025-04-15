"""The tests for recorder platform."""

from __future__ import annotations

from datetime import timedelta

import pytest

from homeassistant.components.input_select import ATTR_OPTIONS, DOMAIN
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import ATTR_EDITABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


@pytest.mark.usefixtures("recorder_mock", "enable_custom_integrations")
async def test_exclude_attributes(hass: HomeAssistant) -> None:
    """Test attributes to be excluded."""
    now = dt_util.utcnow()
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test": {
                    "options": ["first option", "middle option", "last option"],
                    "initial": "middle option",
                }
            }
        },
    )

    state = hass.states.get("input_select.test")
    assert state
    assert state.attributes[ATTR_EDITABLE] is False

    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, hass.states.async_entity_ids()
    )
    assert len(states) >= 1
    for entity_states in states.values():
        for state in entity_states:
            assert ATTR_EDITABLE not in state.attributes
            assert ATTR_OPTIONS in state.attributes
