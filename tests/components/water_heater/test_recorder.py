"""The tests for water_heater recorder."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components import recorder, water_heater
from homeassistant.components.water_heater import (
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_OPERATION_LIST,
)
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(
    recorder_mock: recorder.Recorder, hass: HomeAssistant
) -> None:
    """Test water_heater registered attributes to be excluded."""
    now = dt_util.utcnow()
    await async_setup_component(
        hass, water_heater.DOMAIN, {water_heater.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        recorder.history.get_significant_states,
        hass,
        now,
        None,
        hass.states.async_entity_ids(),
    )
    assert len(states) >= 1
    for entity_states in states.values():
        for state in entity_states:
            assert ATTR_OPERATION_LIST not in state.attributes
            assert ATTR_MIN_TEMP not in state.attributes
            assert ATTR_MAX_TEMP not in state.attributes
            assert ATTR_FRIENDLY_NAME in state.attributes
