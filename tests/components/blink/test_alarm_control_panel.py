"""Test the Blink alarm control panel platform."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_DISARM,
)
from homeassistant.core import HomeAssistant

ENTITY_ID = "alarm_control_panel.blink_sync_module"


@pytest.mark.parametrize(
    ("initial_arm", "service", "expected_arm", "expected_state"),
    [
        pytest.param(
            False,
            SERVICE_ALARM_ARM_AWAY,
            True,
            AlarmControlPanelState.ARMED_AWAY,
            id="arm_away",
        ),
        pytest.param(
            True,
            SERVICE_ALARM_DISARM,
            False,
            AlarmControlPanelState.DISARMED,
            id="disarm",
        ),
    ],
)
async def test_arm_state_updates_when_refresh_is_skipped(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    sync_module: MagicMock,
    initial_arm: bool,
    service: str,
    expected_arm: bool,
    expected_state: AlarmControlPanelState,
) -> None:
    """Test the new arm state shows straight away when BlinkPy skips the refresh.

    BlinkPy skips a refresh that comes too soon after the last one, so the
    state must come from the network info read after the command. See #186556.
    """
    sync_module.arm = initial_arm
    mock_blink_api.sync = {"Sync Module": sync_module}
    mock_blink_api.networks = []

    async def get_network_info() -> bool:
        sync_module.arm = expected_arm
        return True

    sync_module.get_network_info.side_effect = get_network_info

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    assert hass.states.get(ENTITY_ID).state == expected_state
    sync_module.async_arm.assert_awaited_once_with(expected_arm)
    sync_module.get_network_info.assert_awaited_once_with()
