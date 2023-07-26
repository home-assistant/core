"""The tests for climate recorder."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components import climate
from homeassistant.components.climate import (
    ATTR_FAN_MODES,
    ATTR_HVAC_MODES,
    ATTR_MAX_HUMIDITY,
    ATTR_MAX_TEMP,
    ATTR_MIN_HUMIDITY,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODES,
    ATTR_SWING_MODES,
    ATTR_TARGET_TEMP_STEP,
)
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import ATTR_FRIENDLY_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


@pytest.fixture(autouse=True)
async def climate_only() -> None:
    """Enable only the climate platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.CLIMATE],
    ):
        yield


async def test_exclude_attributes(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test climate registered attributes to be excluded."""
    now = dt_util.utcnow()
    await async_setup_component(hass, "homeassistant", {})
    await async_setup_component(
        hass, climate.DOMAIN, {climate.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, hass.states.async_entity_ids()
    )
    assert len(states) > 1
    for entity_states in states.values():
        for state in entity_states:
            assert ATTR_PRESET_MODES not in state.attributes
            assert ATTR_HVAC_MODES not in state.attributes
            assert ATTR_FAN_MODES not in state.attributes
            assert ATTR_SWING_MODES not in state.attributes
            assert ATTR_MIN_TEMP not in state.attributes
            assert ATTR_MAX_TEMP not in state.attributes
            assert ATTR_MIN_HUMIDITY not in state.attributes
            assert ATTR_MAX_HUMIDITY not in state.attributes
            assert ATTR_TARGET_TEMP_STEP not in state.attributes
            assert ATTR_FRIENDLY_NAME in state.attributes
