"""Tests for Bosch Alarm component."""

import asyncio

import pytest

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import MockBoschAlarmConfig

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "bosch_alarm_test_data",
    ["Solution 3000"],
    indirect=True,
)
async def test_update_alarm_device(
    hass: HomeAssistant,
    bosch_alarm_test_data: MockBoschAlarmConfig,
    bosch_config_entry: MockConfigEntry,
) -> None:
    """Test that alarm panel state changes after arming the panel."""
    bosch_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(bosch_config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = "alarm_control_panel.bosch_solution_3000_area1"
    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED
    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_arm_away",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMING
    await asyncio.sleep(0.1)
    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_AWAY
    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_disarm",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED
    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_arm_home",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMING
    await asyncio.sleep(0.1)
    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_HOME
    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_disarm",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED
    assert await hass.config_entries.async_unload(bosch_config_entry.entry_id)
