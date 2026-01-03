"""Test the System Nexa 2 switch platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sn2 import OnOffSetting, StateChange

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_system_nexa_2_device")
async def test_switch_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch entities."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that the relay switch is created
    state = hass.states.get("switch.test_device_relay")
    assert state is not None
    # Entity is unavailable until coordinator receives data
    assert state.state == "unavailable"


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
        {ATTR_ENTITY_ID: "switch.test_device_relay"},
        blocking=True,
    )
    device.turn_on.assert_called_once()

    # Test turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_device_relay"},
        blocking=True,
    )
    device.turn_off.assert_called_once()

    # Test toggle
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "switch.test_device_relay"},
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

    state = hass.states.get("switch.test_device_relay")
    assert state.state == "on"

    # Test with state = 0.0 (off)
    await coordinator._async_handle_update(StateChange(state=0.0))
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_device_relay")
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
    state = hass.states.get("switch.test_device_433mhz")
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
        {ATTR_ENTITY_ID: "switch.test_device_433mhz"},
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
