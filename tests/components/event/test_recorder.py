"""The tests for event recorder."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components import select
from homeassistant.components.event import ATTR_EVENT_TYPES
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import ATTR_FRIENDLY_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.components.recorder.common import async_wait_recording_done


@pytest.fixture(autouse=True)
async def event_only() -> None:
    """Enable only the event platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.EVENT],
    ):
        yield


async def test_exclude_attributes(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test select registered attributes to be excluded."""
    now = dt_util.utcnow()
    assert await async_setup_component(hass, "homeassistant", {})
    await async_setup_component(
        hass, select.DOMAIN, {select.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    hass.bus.async_fire("demo_button_pressed")
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, hass.states.async_entity_ids()
    )
    assert len(states) >= 1
    for entity_states in states.values():
        for state in entity_states:
            assert state
            assert ATTR_EVENT_TYPES not in state.attributes
            assert ATTR_FRIENDLY_NAME in state.attributes
