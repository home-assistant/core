"""The tests for camera recorder."""
from __future__ import annotations

from datetime import timedelta

import pytest

from homeassistant.components import camera
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_PICTURE,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


@pytest.fixture(autouse=True)
async def setup_homeassistant():
    """Override the fixture in calendar.conftest."""


async def test_exclude_attributes(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test camera registered attributes to be excluded."""
    now = dt_util.utcnow()
    await async_setup_component(hass, "homeassistant", {})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
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
            assert "access_token" not in state.attributes
            assert ATTR_ENTITY_PICTURE not in state.attributes
            assert ATTR_ATTRIBUTION not in state.attributes
            assert ATTR_SUPPORTED_FEATURES not in state.attributes
            assert ATTR_FRIENDLY_NAME in state.attributes
