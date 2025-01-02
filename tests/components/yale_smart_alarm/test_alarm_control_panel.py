"""The test for the Yale Smart ALarm alarm control panel platform."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from yalesmartalarmclient import YaleSmartAlarmData

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    AlarmControlPanelState,
)
from homeassistant.const import ATTR_CODE, ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.ALARM_CONTROL_PANEL]],
)
async def test_alarm_control_panel(
    hass: HomeAssistant,
    load_config_entry: tuple[MockConfigEntry, Mock],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Yale Smart Alarm alarm_control_panel."""
    entry = load_config_entry[0]
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.ALARM_CONTROL_PANEL]],
)
async def test_alarm_control_panel_service_calls(
    hass: HomeAssistant,
    get_data: YaleSmartAlarmData,
    load_config_entry: tuple[MockConfigEntry, Mock],
) -> None:
    """Test the Yale Smart Alarm alarm_control_panel action calls."""

    client = load_config_entry[1]

    data = deepcopy(get_data.cycle)
    data["data"] = data["data"].pop("device_status")

    client.auth.get_authenticated = Mock(return_value=data)
    client.disarm = Mock(return_value=True)
    client.arm_partial = Mock(return_value=True)
    client.arm_full = Mock(return_value=True)

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: "alarm_control_panel.test_username", ATTR_CODE: "123456"},
        blocking=True,
    )
    client.disarm.assert_called_once()
    state = hass.states.get("alarm_control_panel.test_username")
    assert state.state == AlarmControlPanelState.DISARMED
    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_HOME,
        {ATTR_ENTITY_ID: "alarm_control_panel.test_username", ATTR_CODE: "123456"},
        blocking=True,
    )
    client.arm_partial.assert_called_once()
    state = hass.states.get("alarm_control_panel.test_username")
    assert state.state == AlarmControlPanelState.ARMED_HOME
    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {ATTR_ENTITY_ID: "alarm_control_panel.test_username", ATTR_CODE: "123456"},
        blocking=True,
    )
    client.arm_full.assert_called_once()
    state = hass.states.get("alarm_control_panel.test_username")
    assert state.state == AlarmControlPanelState.ARMED_AWAY

    client.disarm = Mock(side_effect=ConnectionError("no connection"))

    with pytest.raises(
        HomeAssistantError,
        match="Could not set alarm for test-username: no connection",
    ):
        await hass.services.async_call(
            ALARM_CONTROL_PANEL_DOMAIN,
            SERVICE_ALARM_DISARM,
            {ATTR_ENTITY_ID: "alarm_control_panel.test_username", ATTR_CODE: "123456"},
            blocking=True,
        )

    state = hass.states.get("alarm_control_panel.test_username")
    assert state.state == AlarmControlPanelState.ARMED_AWAY

    client.disarm = Mock(return_value=False)

    with pytest.raises(
        HomeAssistantError,
        match="Could not change alarm, check system ready for arming",
    ):
        await hass.services.async_call(
            ALARM_CONTROL_PANEL_DOMAIN,
            SERVICE_ALARM_DISARM,
            {ATTR_ENTITY_ID: "alarm_control_panel.test_username", ATTR_CODE: "123456"},
            blocking=True,
        )

    state = hass.states.get("alarm_control_panel.test_username")
    assert state.state == AlarmControlPanelState.ARMED_AWAY


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.ALARM_CONTROL_PANEL]],
)
async def test_alarm_control_panel_not_available(
    hass: HomeAssistant,
    get_data: YaleSmartAlarmData,
    load_config_entry: tuple[MockConfigEntry, Mock],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Yale Smart Alarm alarm_control_panel not being available."""

    client = load_config_entry[1]
    client.get_armed_status = Mock(return_value=None)

    state = hass.states.get("alarm_control_panel.test_username")
    assert state.state == AlarmControlPanelState.ARMED_AWAY

    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("alarm_control_panel.test_username")
    assert state.state == STATE_UNAVAILABLE
