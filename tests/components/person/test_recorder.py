"""The tests for update recorder."""
from __future__ import annotations

from homeassistant.components.person import (
    ATTR_DEVICE_TRACKERS,
    ATTR_SOURCE,
    ATTR_USER_ID,
    DOMAIN,
    async_add_user_device_tracker,
)
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import ATTR_ID, ATTR_LATITUDE, ATTR_LONGITUDE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockUser
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    enable_custom_integrations: None,
) -> None:
    """Test update attributes to be excluded."""
    user_id = hass_admin_user.id
    config = {
        DOMAIN: {
            "id": "1234",
            "name": "test person",
            "user_id": user_id,
            "device_trackers": [],
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    state = hass.states.get("person.test_person")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ID) == "1234"
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) is None
    assert state.attributes.get(ATTR_USER_ID) == user_id

    await hass.async_block_till_done()
    async_add_user_device_tracker(hass, "person.test_person", "device_tracker.test")
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states,
        hass,
        dt_util.utcnow(),
        None,
        hass.states.async_entity_ids(),
    )
    assert len(states) >= 1
    for entity_states in states.values():
        for state in entity_states:
            assert ATTR_DEVICE_TRACKERS not in state.attributes
