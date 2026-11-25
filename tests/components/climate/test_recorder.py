"""The tests for climate recorder."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import async_fire_time_changed
from pytest_homeassistant.components.recorder.common import async_wait_recording_done

from homeassistant.components import climate
from homeassistant.components.climate import ClimateEntityCapabilityAttribute
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import EntityStateAttribute, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util


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
            assert ClimateEntityCapabilityAttribute.FAN_MODES not in state.attributes
            assert EntityStateAttribute.FRIENDLY_NAME in state.attributes
            assert ClimateEntityCapabilityAttribute.HVAC_MODES not in state.attributes
            assert ClimateEntityCapabilityAttribute.SWING_MODES not in state.attributes
            assert ClimateEntityCapabilityAttribute.MAX_HUMIDITY not in state.attributes
            assert ClimateEntityCapabilityAttribute.MAX_TEMP not in state.attributes
            assert ClimateEntityCapabilityAttribute.MIN_HUMIDITY not in state.attributes
            assert ClimateEntityCapabilityAttribute.MIN_TEMP not in state.attributes
            assert ClimateEntityCapabilityAttribute.PRESET_MODES not in state.attributes
            assert (
                ClimateEntityCapabilityAttribute.TARGET_HUMIDITY_STEP
                not in state.attributes
            )
            assert (
                ClimateEntityCapabilityAttribute.TARGET_TEMP_STEP
                not in state.attributes
            )
