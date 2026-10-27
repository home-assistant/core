"""The tests for recorder platform."""

from datetime import timedelta

import pytest
from pytest_homeassistant.common import async_fire_time_changed
from pytest_homeassistant.components.recorder.common import async_wait_recording_done

from homeassistant.components.input_text import DOMAIN, MODE_TEXT
from homeassistant.components.input_text.const import InputTextEntityStateAttribute
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.text import TextEntityCapabilityAttribute
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util


@pytest.mark.usefixtures("recorder_mock", "enable_custom_integrations")
async def test_exclude_attributes(hass: HomeAssistant) -> None:
    """Test attributes to be excluded."""
    now = dt_util.utcnow()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"test": {}}})

    state = hass.states.get("input_text.test")
    assert state
    assert state.attributes[InputTextEntityStateAttribute.EDITABLE] is False
    assert state.attributes[TextEntityCapabilityAttribute.MAX] == 100
    assert state.attributes[TextEntityCapabilityAttribute.MIN] == 0
    assert state.attributes[TextEntityCapabilityAttribute.MODE] == MODE_TEXT
    assert state.attributes[TextEntityCapabilityAttribute.PATTERN] is None

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
            assert InputTextEntityStateAttribute.EDITABLE not in state.attributes
            assert TextEntityCapabilityAttribute.MAX not in state.attributes
            assert TextEntityCapabilityAttribute.MIN not in state.attributes
            assert TextEntityCapabilityAttribute.MODE not in state.attributes
            assert TextEntityCapabilityAttribute.PATTERN not in state.attributes
