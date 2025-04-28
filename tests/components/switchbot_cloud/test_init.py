"""Tests for the SwitchBot Cloud integration init."""

from unittest.mock import patch

import pytest
from switchbot_api import CannotConnect, Device, InvalidAuth, PowerState, Remote

from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant

from . import configure_integration


@pytest.fixture
def mock_list_devices():
    """Mock list_devices."""
    with patch.object(SwitchBotAPI, "list_devices") as mock_list_devices:
        yield mock_list_devices


@pytest.fixture
def mock_get_status():
    """Mock get_status."""
    with patch.object(SwitchBotAPI, "get_status") as mock_get_status:
        yield mock_get_status


async def test_setup_entry_success(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test successful setup of entry."""
    mock_list_devices.return_value = [
        Remote(
            deviceId="air-conditonner-id-1",
            deviceName="air-conditonner-name-1",
            remoteType="Air Conditioner",
            hubDeviceId="test-hub-id",
        ),
        Device(
            deviceId="plug-id-1",
            deviceName="plug-name-1",
            deviceType="Plug",
            hubDeviceId="test-hub-id",
        ),
        Remote(
            deviceId="plug-id-2",
            deviceName="plug-name-2",
            remoteType="DIY Plug",
            hubDeviceId="test-hub-id",
        ),
        Remote(
            deviceId="meter-pro-1",
            deviceName="meter-pro-name-1",
            deviceType="MeterPro(CO2)",
            hubDeviceId="test-hub-id",
        ),
        Remote(
            deviceId="hub2-1",
            deviceName="hub2-name-1",
            deviceType="Hub 2",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.return_value = {"power": PowerState.ON.value}
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    mock_list_devices.assert_called_once()
    mock_get_status.assert_called()


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (InvalidAuth, ConfigEntryState.SETUP_ERROR),
        (CannotConnect, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_fails_when_listing_devices(
    hass: HomeAssistant,
    error: Exception,
    state: ConfigEntryState,
    mock_list_devices,
    mock_get_status,
) -> None:
    """Test error handling when list_devices in setup of entry."""
    mock_list_devices.side_effect = error
    entry = await configure_integration(hass)
    assert entry.state == state

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    mock_list_devices.assert_called_once()
    mock_get_status.assert_not_called()


async def test_setup_entry_fails_when_refreshing(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test error handling in get_status in setup of entry."""
    mock_list_devices.return_value = [
        Device(
            deviceId="test-id",
            deviceName="test-name",
            deviceType="Plug",
            hubDeviceId="test-hub-id",
        )
    ]
    mock_get_status.side_effect = CannotConnect
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    mock_list_devices.assert_called_once()
    mock_get_status.assert_called()
