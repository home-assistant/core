"""Tests for the Rainforest RAVEn data coordinator."""
from xml.etree.ElementTree import ParseError

import pytest
from serial.serialutil import SerialException

from homeassistant.components.rainforest_raven.data import RAVEnDataCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from . import create_mock_device, create_mock_entry
from .const import DEVICE_INFO

from tests.common import patch


@pytest.fixture
def mock_device():
    """Mock a functioning RAVEn device."""
    mock_device = create_mock_device()
    with patch(
        "homeassistant.components.rainforest_raven.data.RAVEnSerialDevice",
        return_value=mock_device,
    ):
        yield mock_device


async def test_coordinator_device_info(hass: HomeAssistant, mock_device):
    """Test reporting device information from the coordinator."""
    entry = create_mock_entry()
    coordinator = RAVEnDataCoordinator(hass, entry)

    assert coordinator.device_fw_version is None
    assert coordinator.device_hw_version is None
    assert coordinator.device_mac_address is None
    assert coordinator.device_manufacturer is None
    assert coordinator.device_model is None
    assert coordinator.device_name == "RAVEn Device"

    await coordinator.async_config_entry_first_refresh()

    assert coordinator.device_fw_version == "2.0.0 (7400)"
    assert coordinator.device_hw_version == "2.7.3"
    assert coordinator.device_mac_address
    assert coordinator.device_manufacturer == "Rainforest Automation, Inc."
    assert coordinator.device_model == "Z105-2-EMU2-LEDD_JM"
    assert coordinator.device_name == "RAVEn Device"


async def test_coordinator_cache_device(hass: HomeAssistant, mock_device):
    """Test that the device isn't re-opened for subsequent refreshes."""
    entry = create_mock_entry()
    coordinator = RAVEnDataCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()
    assert mock_device.get_network_info.call_count == 1
    assert mock_device.open.call_count == 1

    await coordinator.async_refresh()
    assert mock_device.get_network_info.call_count == 2
    assert mock_device.open.call_count == 1


async def test_coordinator_device_error_setup(hass: HomeAssistant, mock_device):
    """Test handling of a device error during initialization."""
    entry = create_mock_entry()
    coordinator = RAVEnDataCoordinator(hass, entry)

    mock_device.get_network_info.side_effect = SerialException
    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()


async def test_coordinator_device_error_update(hass: HomeAssistant, mock_device):
    """Test handling of a device error during an update."""
    entry = create_mock_entry()
    coordinator = RAVEnDataCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()
    assert coordinator.last_update_success is True

    mock_device.get_network_info.side_effect = SerialException
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False


async def test_coordinator_parse_error(hass: HomeAssistant, mock_device):
    """Test handling of an error parsing raw device data."""
    entry = create_mock_entry()
    coordinator = RAVEnDataCoordinator(hass, entry)

    mock_device.get_device_info.side_effect = ParseError
    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()
    assert mock_device.get_device_info.call_count == 4


async def test_coordinator_parse_error_recovery(hass: HomeAssistant, mock_device):
    """Test retry logic for handling raw device data parsing errors."""
    entry = create_mock_entry()
    coordinator = RAVEnDataCoordinator(hass, entry)

    raise_error = True

    def get_device_info(meter=None):
        nonlocal raise_error
        if raise_error:
            raise_error = False
            raise ParseError()
        return DEVICE_INFO

    mock_device.get_device_info.side_effect = get_device_info
    await coordinator.async_config_entry_first_refresh()
    assert coordinator.last_update_success is True
    assert mock_device.get_device_info.call_count == 2
