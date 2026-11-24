"""Tests for the IRM KMI recorder exclusions."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.recorder.common import async_wait_recording_done

from homeassistant.components.recorder.history import get_significant_states
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from . import setup_integration
from .const import RADAR_ENTITY_ID, WARNING_ENTITY_ID


@pytest.mark.usefixtures("recorder_mock", "mock_irm_kmi_api")
async def test_exclude_attributes_radar(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the radar hint is not recorded."""
    now = dt_util.utcnow()
    await setup_integration(hass, mock_config_entry)
    radar_state = hass.states.get(RADAR_ENTITY_ID)
    assert radar_state is not None
    assert radar_state.attributes["hint"]
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, [RADAR_ENTITY_ID]
    )
    assert len(states[RADAR_ENTITY_ID]) == 1
    assert "hint" not in states[RADAR_ENTITY_ID][0].attributes
    recorded_state = states[RADAR_ENTITY_ID][0]
    assert isinstance(recorded_state, State)
    assert "hint" not in recorded_state.attributes


@pytest.mark.usefixtures("recorder_mock", "mock_irm_kmi_api")
async def test_exclude_attributes_warning(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the warnings are not recorded."""
    now = dt_util.utcnow()
    await setup_integration(hass, mock_config_entry)
    assert "warnings" in hass.states.get(WARNING_ENTITY_ID).attributes
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, [WARNING_ENTITY_ID]
    )
    assert len(states[WARNING_ENTITY_ID]) == 1
    assert "warnings" not in states[WARNING_ENTITY_ID][0].attributes
