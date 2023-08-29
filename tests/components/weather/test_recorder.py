"""The tests for weather recorder."""
from __future__ import annotations

from datetime import timedelta

import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.weather import ATTR_FORECAST
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


@pytest.mark.parametrize(
    "setup", ["mock_setup", "mock_config_entry_setup"], indirect=True
)
async def test_exclude_attributes(
    recorder_mock: Recorder, hass: HomeAssistant, setup: str
) -> None:
    """Test weather attributes to be excluded."""
    now = dt_util.utcnow()
    hass.config.units = METRIC_SYSTEM
    await hass.async_block_till_done()

    state = hass.states.get("weather.test")
    assert state.attributes[ATTR_FORECAST]

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
            assert ATTR_FORECAST not in state.attributes
