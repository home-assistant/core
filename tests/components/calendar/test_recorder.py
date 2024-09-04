"""The tests for calendar recorder."""

from datetime import timedelta

import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


@pytest.fixture(autouse=True)
async def mock_setup_dependencies(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    set_time_zone: None,
    mock_setup_integration: None,
    config_entry: MockConfigEntry,
) -> None:
    """Fixture that ensures the recorder is setup in the right order."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_exclude_attributes(hass: HomeAssistant) -> None:
    """Test sensor attributes to be excluded."""
    now = dt_util.utcnow()

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
