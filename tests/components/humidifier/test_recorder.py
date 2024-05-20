"""The tests for humidifier recorder."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components import humidifier
from homeassistant.components.humidifier import (
    ATTR_AVAILABLE_MODES,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
)
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test humidifier registered attributes to be excluded."""
    now = dt_util.utcnow()
    await async_setup_component(
        hass, humidifier.DOMAIN, {humidifier.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, hass.states.async_entity_ids()
    )
    assert len(states) >= 1
    for state in (
        state
        for entity_states in states.values()
        for state in entity_states
        if split_entity_id(state.entity_id)[0] == humidifier.DOMAIN
    ):
        assert ATTR_MIN_HUMIDITY not in state.attributes
        assert ATTR_MAX_HUMIDITY not in state.attributes
        assert ATTR_AVAILABLE_MODES not in state.attributes
        assert ATTR_FRIENDLY_NAME in state.attributes
