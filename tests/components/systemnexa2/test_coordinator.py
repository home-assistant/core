"""Test the System Nexa 2 coordinator."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sn2 import (
    ConnectionStatus,
    DeviceInitializationError,
    OnOffSetting,
    SettingsUpdate,
    StateChange,
)

from homeassistant.components.systemnexa2.coordinator import (
    SystemNexa2DataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


async def test_coordinator_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device,
) -> None:
    """Test coordinator setup failure raises ConfigEntryNotReady."""

    mock_system_nexa_2_device.initiate_device = AsyncMock(
        side_effect=DeviceInitializationError("Test error")
    )

    coordinator = SystemNexa2DataUpdateCoordinator(hass, mock_config_entry)

    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_setup()


@pytest.mark.usefixtures("mock_system_nexa_2_device")
async def test_coordinator_connection_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator handles connection status updates."""
    coordinator = SystemNexa2DataUpdateCoordinator(hass, mock_config_entry)
    await coordinator.async_setup()

    # Set up initial data so device can become available
    coordinator.data.on_off_settings = {}
    await coordinator._async_handle_update(StateChange(state=1.0))

    # Simulate disconnection
    await coordinator._async_handle_update(ConnectionStatus(connected=False))
    assert not coordinator.data.available
    assert "Device 192.168.1.100 is unavailable" in caplog.text

    # Simulate reconnection - need to resend state to make device available again
    caplog.clear()
    await coordinator._async_handle_update(ConnectionStatus(connected=True))
    await coordinator._async_handle_update(StateChange(state=1.0))
    assert coordinator.data.available
    assert "Device 192.168.1.100 is back online" in caplog.text


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
