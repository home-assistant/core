"""The tests for sun recorder."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.sun import DOMAIN
from homeassistant.components.sun.entity import (
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
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test sun attributes to be excluded."""
    now = dt_util.utcnow()
    await async_setup_component(hass, DOMAIN, {})
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
