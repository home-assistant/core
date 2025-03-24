"""The tests for recorder platform."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.schedule.const import ATTR_NEXT_EVENT, DOMAIN
from homeassistant.const import ATTR_EDITABLE, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


@pytest.mark.usefixtures("recorder_mock", "enable_custom_integrations")
async def test_exclude_attributes(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test attributes to be excluded."""
    freezer.move_to("2024-08-02 06:30:00-07:00")  # Before Friday event
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
                    "friday": [
                        {"from": "7:00", "to": "8:00", "data": {"party_level": "epic"}}
                    ],
                    "saturday": [{"from": "9:00", "to": "10:00"}],
                    "sunday": [
                        {"from": "11:00", "to": "12:00", "data": {"entry": "VIPs only"}}
                    ],
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

    # Move to during Friday event
    freezer.move_to("2024-08-02 07:30:00-07:00")
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()
    state = hass.states.get("schedule.test")
    assert "entry" not in state.attributes
    assert state.attributes["party_level"] == "epic"

    # Move to during Sunday event
    freezer.move_to("2024-08-04 11:30:00-07:00")
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()
    state = hass.states.get("schedule.test")
    assert "party_level" not in state.attributes
    assert state.attributes["entry"] == "VIPs only"

    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
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
            assert "entry" not in state.attributes
            assert "party_level" not in state.attributes
