"""The tests for calendar recorder."""
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import ATTR_FRIENDLY_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


@pytest.fixture(autouse=True)
async def setup_homeassistant():
    """Override the fixture in calendar.conftest."""


@pytest.fixture(autouse=True)
async def calendar_only() -> None:
    """Enable only the calendar platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.CALENDAR],
    ):
        yield


async def test_exclude_attributes(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test sensor attributes to be excluded."""
    now = dt_util.utcnow()
    await async_setup_component(hass, "homeassistant", {})
    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.calendar_1")
    assert state
    assert ATTR_FRIENDLY_NAME in state.attributes
    assert "description" in state.attributes

    # calendar.calendar_1
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, hass.states.async_entity_ids()
    )
    assert len(states) > 1
    for entity_states in states.values():
        for state in entity_states:
            assert ATTR_FRIENDLY_NAME in state.attributes
            assert "description" not in state.attributes
