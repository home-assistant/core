"""The tests for update recorder."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.person import ATTR_DEVICE_TRACKERS, DOMAIN
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """Test update attributes to be excluded."""
    now = dt_util.utcnow()
    config = {
        DOMAIN: {
            "id": "1234",
            "name": "test person",
            "user_id": "test_user_id",
            "device_trackers": ["device_tracker.test"],
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)

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
            assert ATTR_DEVICE_TRACKERS not in state.attributes
