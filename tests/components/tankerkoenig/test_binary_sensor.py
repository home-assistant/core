"""Tests for the Tankerkoening integration."""

from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.tankerkoenig.const import ATTR_OPENING_TIMES
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import STATION

from tests.common import MockConfigEntry
from tests.components.recorder.common import async_wait_recording_done


@pytest.mark.usefixtures("setup_integration")
async def test_binary_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the tankerkoenig binary sensors."""

    state = hass.states.get("binary_sensor.station_somewhere_street_1_status")
    assert state
    assert state.state == STATE_ON
    assert state.attributes == snapshot


async def test_binary_sensor_whole_day(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tankerkoenig: AsyncMock,
) -> None:
    """Test a station open around the clock reports it as its opening time."""
    tankerkoenig.station_details.return_value = replace(
        STATION, whole_day=True, opening_times=[]
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.station_somewhere_street_1_status")
    assert state
    assert state.attributes["opening_times"] == [
        {"text": "Mo-So", "start": "00:00:00", "end": "24:00:00"}
    ]
    assert "whole_day" not in state.attributes


async def test_opening_times_not_recorded(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tankerkoenig: AsyncMock,
) -> None:
    """Test the opening times stay out of the recorder."""
    now = dt_util.utcnow()
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    entity_id = "binary_sensor.station_somewhere_street_1_status"
    assert ATTR_OPENING_TIMES in hass.states.get(entity_id).attributes

    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, [entity_id]
    )
    assert states[entity_id]
    for state in states[entity_id]:
        assert ATTR_OPENING_TIMES not in state.attributes
