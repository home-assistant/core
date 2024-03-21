"""The tests for recorder platform."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.input_datetime import CONF_HAS_DATE, CONF_HAS_TIME, DOMAIN
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import ATTR_EDITABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(
    recorder_mock: Recorder, hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test attributes to be excluded."""
    now = dt_util.utcnow()
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"test": {CONF_HAS_TIME: True}}}
    )

    state = hass.states.get("input_datetime.test")
    assert state
    assert state.attributes[ATTR_EDITABLE] is False
    assert state.attributes[CONF_HAS_DATE] is False
    assert state.attributes[CONF_HAS_TIME] is True

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
            assert ATTR_EDITABLE not in state.attributes
            assert CONF_HAS_DATE not in state.attributes
            assert CONF_HAS_TIME not in state.attributes
