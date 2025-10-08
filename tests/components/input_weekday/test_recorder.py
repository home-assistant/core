"""Tests for the Input Weekday recorder."""

from homeassistant.components.input_weekday import ATTR_EDITABLE, ATTR_WEEKDAYS
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test that certain attributes are excluded."""
    now = dt_util.utcnow()
    assert await async_setup_component(
        hass,
        "input_weekday",
        {"input_weekday": {"test": {"weekdays": ["mon", "wed"]}}},
    )

    state = hass.states.get("input_weekday.test")
    assert state.attributes[ATTR_WEEKDAYS] == ["mon", "wed"]
    assert state.attributes[ATTR_EDITABLE] is False

    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, ["input_weekday.test"]
    )
    assert len(states) == 1
    for entity_states in states.values():
        for state in entity_states:
            assert ATTR_WEEKDAYS in state.attributes
            assert ATTR_EDITABLE not in state.attributes
            assert ATTR_FRIENDLY_NAME in state.attributes
