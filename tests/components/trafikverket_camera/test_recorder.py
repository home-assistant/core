"""The tests for Trafikcerket Camera recorder."""

from __future__ import annotations

import pytest
from pytrafikverket.trafikverket_camera import CameraInfo

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.components.recorder.common import async_wait_recording_done
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_exclude_attributes(
    recorder_mock: Recorder,
    entity_registry_enabled_by_default: None,
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    aioclient_mock: AiohttpClientMocker,
    get_camera: CameraInfo,
) -> None:
    """Test camera has description and location excluded from recording."""
    state1 = hass.states.get("camera.test_camera")
    assert state1.state == "idle"
    assert state1.attributes["description"] == "Test Camera for testing"
    assert state1.attributes["location"] == "Test location"
    assert state1.attributes["type"] == "Road"
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states,
        hass,
        dt_util.now(),
        None,
        hass.states.async_entity_ids(),
    )
    assert len(states) == 8
    assert states.get("camera.test_camera")
    for entity_states in states.values():
        for state in entity_states:
            if state.entity_id == "camera.test_camera":
                assert "location" not in state.attributes
                assert "description" not in state.attributes
                assert "type" in state.attributes
                break
