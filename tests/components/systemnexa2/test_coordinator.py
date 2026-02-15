"""Test the System Nexa 2 coordinator."""

from unittest.mock import MagicMock

import pytest
from sn2 import (
    ConnectionStatus,
    OnOffSetting,
    SettingsUpdate,
    StateChange,
)

from homeassistant.components.systemnexa2.coordinator import (
    SystemNexa2DataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_system_nexa_2_device")
async def test_coordinator_connection_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles connection status updates."""
    coordinator = SystemNexa2DataUpdateCoordinator(hass, mock_config_entry)
    await coordinator.async_setup()

    # Set up initial data so device can become available
    coordinator.data.on_off_settings = {}
    await coordinator._async_handle_update(StateChange(state=1.0))
    assert coordinator.last_update_success

    # Simulate disconnection
    await coordinator._async_handle_update(ConnectionStatus(connected=False))
    assert not coordinator.last_update_success

    # Simulate reconnection - need to resend state to make device available again
    await coordinator._async_handle_update(ConnectionStatus(connected=True))
    await coordinator._async_handle_update(StateChange(state=1.0))
    assert coordinator.last_update_success


@pytest.mark.usefixtures("mock_system_nexa_2_device")
async def test_coordinator_state_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles state change updates."""
    coordinator = SystemNexa2DataUpdateCoordinator(hass, mock_config_entry)
    await coordinator.async_setup()

    # Simulate state change
    await coordinator._async_handle_update(StateChange(state=0.5))
    assert coordinator.data.state == 0.5
    assert coordinator._state_received_once is True


@pytest.mark.usefixtures("mock_system_nexa_2_device")
async def test_coordinator_settings_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles settings updates."""
    coordinator = SystemNexa2DataUpdateCoordinator(hass, mock_config_entry)
    await coordinator.async_setup()

    # Create a mock OnOffSetting that passes isinstance check
    mock_setting = MagicMock(spec=OnOffSetting)
    mock_setting.name = "test_setting"

    # Simulate settings update
    await coordinator._async_handle_update(SettingsUpdate(settings=[mock_setting]))
    assert "test_setting" in coordinator.data.on_off_settings
    assert coordinator.data.on_off_settings["test_setting"] == mock_setting
