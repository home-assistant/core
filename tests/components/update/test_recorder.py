"""The tests for update recorder."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.update.const import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_RELEASE_SUMMARY,
    DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_PICTURE, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import MockUpdateEntity

from tests.common import async_fire_time_changed, setup_test_component_platform
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_update_entities: list[MockUpdateEntity],
) -> None:
    """Test update attributes to be excluded."""
    now = dt_util.utcnow()
    setup_test_component_platform(hass, DOMAIN, mock_update_entities)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()
    state = hass.states.get("update.update_already_in_progress")
    assert state.attributes[ATTR_IN_PROGRESS] == 50
    assert (
        state.attributes[ATTR_ENTITY_PICTURE]
        == "https://brands.home-assistant.io/_/test/icon.png"
    )
    await async_setup_component(hass, DOMAIN, {})

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
            assert ATTR_ENTITY_PICTURE not in state.attributes
            assert ATTR_IN_PROGRESS not in state.attributes
            assert ATTR_RELEASE_SUMMARY not in state.attributes
            assert ATTR_INSTALLED_VERSION in state.attributes
