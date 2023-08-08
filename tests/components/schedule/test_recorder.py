"""The tests for recorder platform."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.schedule.const import ATTR_NEXT_EVENT, DOMAIN
from homeassistant.const import ATTR_EDITABLE, ATTR_FRIENDLY_NAME, ATTR_ICON
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
    """Test attributes to be excluded."""
    now = dt_util.utcnow()
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test": {
                    "name": "Party mode",
                    "icon": "mdi:party-popper",
                    "monday": [{"from": "1:00", "to": "2:00"}],
                    "tuesday": [{"from": "2:00", "to": "3:00"}],
                    "wednesday": [{"from": "3:00", "to": "4:00"}],
                    "thursday": [{"from": "5:00", "to": "6:00"}],
                    "friday": [{"from": "7:00", "to": "8:00"}],
                    "saturday": [{"from": "9:00", "to": "10:00"}],
                    "sunday": [{"from": "11:00", "to": "12:00"}],
                }
            }
        },
    )

    state = hass.states.get("schedule.test")
    assert state
    assert state.attributes[ATTR_EDITABLE] is False
    assert state.attributes[ATTR_FRIENDLY_NAME]
    assert state.attributes[ATTR_ICON]
    assert state.attributes[ATTR_NEXT_EVENT]

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
            assert ATTR_FRIENDLY_NAME in state.attributes
            assert ATTR_ICON in state.attributes
            assert ATTR_NEXT_EVENT not in state.attributes
