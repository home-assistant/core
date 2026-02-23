"""Test the System Nexa 2 switch platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sn2 import ConnectionStatus, OnOffSetting, SettingsUpdate, StateChange
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import find_update_callback

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_system_nexa_2_device")
async def test_switch_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch entities."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_turn_on_off_toggle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device,
) -> None:
    """Test switch turn on, turn off, and toggle."""
    device = mock_system_nexa_2_device.return_value
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the coordinator and update it with state
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry
    coordinator = entry.runtime_data
    await coordinator._async_handle_update(StateChange(state=0.0))
    await hass.async_block_till_done()

    # Test turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_device_relay_1"},
        blocking=True,
    )
    device.turn_on.assert_called_once()

    # Test turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_device_relay_1"},
        blocking=True,
    )
    device.turn_off.assert_called_once()

    # Test toggle
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "switch.test_device_relay_1"},
        blocking=True,
    )
    device.toggle.assert_called_once()


async def test_switch_is_on_property(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device,
) -> None:
    """Test switch is_on property."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the coordinator and update it with state
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    coordinator = entry.runtime_data

    # Test with state = 1.0 (on)
    await coordinator._async_handle_update(StateChange(state=1.0))
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_device_relay_1")
    assert state.state == "on"

    # Test with state = 0.0 (off)
    await coordinator._async_handle_update(StateChange(state=0.0))
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_device_relay_1")
    assert state.state == "off"


async def test_configuration_switches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device,
) -> None:
    """Test configuration switch entities."""
    device = mock_system_nexa_2_device.return_value

    # Create mock OnOffSettings with keys matching SWITCH_TYPES
    mock_setting_433mhz = MagicMock(spec=OnOffSetting)
    mock_setting_433mhz.name = "433Mhz"  # Must match key in SWITCH_TYPES
    mock_setting_433mhz.enable = AsyncMock()
    mock_setting_433mhz.disable = AsyncMock()
    mock_setting_433mhz.is_enabled = MagicMock(return_value=True)

    mock_setting_cloud = MagicMock(spec=OnOffSetting)
    mock_setting_cloud.name = "Cloud Access"  # Must match key in SWITCH_TYPES
    mock_setting_cloud.enable = AsyncMock()
    mock_setting_cloud.disable = AsyncMock()
    mock_setting_cloud.is_enabled = MagicMock(return_value=False)

    # Set settings before setup
    device.settings = [mock_setting_433mhz, mock_setting_cloud]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Make coordinator data available
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    coordinator = entry.runtime_data
    await coordinator._async_handle_update(StateChange(state=1.0))
    await hass.async_block_till_done()

    # Check 433mhz switch state (should be on)
    state = hass.states.get("switch.test_device_433_mhz")
    assert state is not None
    assert state.state == "on"

    # Check cloud_access switch state (should be off)
    state = hass.states.get("switch.test_device_cloud_access")
    assert state is not None
    assert state.state == "off"

    # Test turn off 433mhz
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_device_433_mhz"},
        blocking=True,
    )
    mock_setting_433mhz.disable.assert_called_once_with(device)

    # Test turn on cloud_access
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_device_cloud_access"},
        blocking=True,
    )
    mock_setting_cloud.enable.assert_called_once_with(device)


async def test_coordinator_connection_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test coordinator handles connection status updates."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Find the callback that was registered with the device
    update_callback = find_update_callback(mock_system_nexa_2_device)

    # Initially, the relay switch should be off (state=1.0 from fixture)
    state = hass.states.get("switch.test_device_relay_1")
    assert state is not None
    assert state.state == STATE_ON

    # Simulate device disconnection
    await update_callback(ConnectionStatus(connected=False))
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_device_relay_1")
    assert state.state == STATE_UNAVAILABLE

    # Simulate reconnection and state update
    await update_callback(ConnectionStatus(connected=True))
    await update_callback(StateChange(state=1.0))
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_device_relay_1")
    assert state.state == STATE_ON


async def test_coordinator_state_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test coordinator handles state change updates."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Find the callback that was registered with the device
    update_callback = find_update_callback(mock_system_nexa_2_device)

    # Change state to off (0.0)
    await update_callback(StateChange(state=0.0))
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_device_relay_1")
    assert state is not None
    assert state.state == STATE_OFF

    # Change state to on (1.0)
    await update_callback(StateChange(state=1.0))
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_device_relay_1")
    assert state.state == STATE_ON


async def test_coordinator_settings_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test coordinator handles settings updates."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Find the callback that was registered with the device
    update_callback = find_update_callback(mock_system_nexa_2_device)

    # Get initial state of 433Mhz switch (should be on from fixture)
    state = hass.states.get("switch.test_device_433_mhz")
    assert state is not None
    assert state.state == STATE_ON

    # Get the settings from the device mock and change 433Mhz to disabled
    device = mock_system_nexa_2_device.return_value
    device.settings[0].is_enabled.return_value = False  # 433Mhz

    # Simulate settings update where 433Mhz is now disabled
    await update_callback(SettingsUpdate(settings=device.settings))
    # Need state update to trigger coordinator data update
    await update_callback(StateChange(state=1.0))
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_device_433_mhz")
    assert state.state == STATE_OFF
