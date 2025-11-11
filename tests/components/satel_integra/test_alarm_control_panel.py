"""Test Satel Integra alarm panel."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from satel_integra.satel_integra import AlarmState
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.satel_integra.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import MOCK_ENTRY_ID, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def alarm_control_panel_only() -> AsyncGenerator[None]:
    """Enable only the alarm panel platform."""
    with patch(
        "homeassistant.components.satel_integra.PLATFORMS",
        [Platform.ALARM_CONTROL_PANEL],
    ):
        yield


@pytest.mark.usefixtures("mock_satel")
async def test_alarm_control_panel(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry_with_subentries: MockConfigEntry,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
) -> None:
    """Test switch correctly being set up."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    await snapshot_platform(hass, entity_registry, snapshot, MOCK_ENTRY_ID)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "1234567890_alarm_panel_1")}
    )

    assert device_entry == snapshot(name="device")


async def test_switch_initial_state_on(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test switch has a correct initial state ON after initialization."""
    mock_satel.partition_states = {AlarmState.ARMED_MODE0: [1]}

    await setup_integration(hass, mock_config_entry_with_subentries)

    assert (
        hass.states.get("alarm_control_panel.home").state
        == AlarmControlPanelState.ARMED_AWAY
    )


@pytest.mark.parametrize(
    ("source_state", "resulting_state"),
    [
        (AlarmState.TRIGGERED, AlarmControlPanelState.TRIGGERED),
        (AlarmState.TRIGGERED_FIRE, AlarmControlPanelState.TRIGGERED),
        (AlarmState.ENTRY_TIME, AlarmControlPanelState.PENDING),
        (AlarmState.ARMED_MODE3, AlarmControlPanelState.ARMED_HOME),
        (AlarmState.ARMED_MODE2, AlarmControlPanelState.ARMED_HOME),
        (AlarmState.ARMED_MODE1, AlarmControlPanelState.ARMED_HOME),
        (AlarmState.ARMED_MODE0, AlarmControlPanelState.ARMED_AWAY),
        (AlarmState.EXIT_COUNTDOWN_OVER_10, AlarmControlPanelState.ARMING),
        (AlarmState.EXIT_COUNTDOWN_UNDER_10, AlarmControlPanelState.ARMING),
    ],
)
async def test_alarm_status_callback(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    source_state: AlarmState,
    resulting_state: AlarmControlPanelState,
) -> None:
    """Test alarm control panel correctly changes state after a callback from the panel."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    assert (
        hass.states.get("alarm_control_panel.home").state
        == AlarmControlPanelState.DISARMED
    )

    monitor_status_call = mock_satel.monitor_status.call_args_list[0][0]
    alarm_panel_update_method = monitor_status_call[0]

    mock_satel.partition_states = {source_state: [1]}

    alarm_panel_update_method()
    assert hass.states.get("alarm_control_panel.home").state == resulting_state


# async def test_switch_change_state(
#     hass: HomeAssistant,
#     mock_satel: AsyncMock,
#     mock_config_entry_with_subentries: MockConfigEntry,
# ) -> None:
#     """Test switch correctly changes state after a callback from the panel."""
#     await setup_integration(hass, mock_config_entry_with_subentries)

#     assert hass.states.get("switch.switchable_output").state == STATE_OFF

#     # Test turn on
#     await hass.services.async_call(
#         SWITCH_DOMAIN,
#         SERVICE_TURN_ON,
#         {ATTR_ENTITY_ID: "switch.switchable_output"},
#         blocking=True,
#     )

#     assert hass.states.get("switch.switchable_output").state == STATE_ON
#     mock_satel.set_output.assert_awaited_once_with(MOCK_CODE, 1, True)

#     mock_satel.set_output.reset_mock()

#     # Test turn off
#     await hass.services.async_call(
#         SWITCH_DOMAIN,
#         SERVICE_TURN_OFF,
#         {ATTR_ENTITY_ID: "switch.switchable_output"},
#         blocking=True,
#     )

#     assert hass.states.get("switch.switchable_output").state == STATE_OFF
#     mock_satel.set_output.assert_awaited_once_with(MOCK_CODE, 1, False)
