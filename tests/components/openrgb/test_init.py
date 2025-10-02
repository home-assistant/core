"""Tests for the OpenRGB integration init."""

import socket
from unittest.mock import MagicMock

from openrgb.utils import ControllerParsingError, OpenRGBDisconnected, SDKVersionError
import pytest

from homeassistant.components.openrgb.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_entry_setup_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
) -> None:
    """Test entry setup and unload."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_openrgb_client.disconnect.called


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_server_device_registry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test server device is created in device registry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    device_registry = dr.async_get(hass)
    server_device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )

    assert server_device
    assert server_device.name == "OpenRGB (127.0.0.1:6742)"
    assert server_device.manufacturer == "OpenRGB"
    assert server_device.model == "OpenRGB SDK Server"
    assert server_device.sw_version == "3 (Protocol)"
    assert server_device.entry_type is dr.DeviceEntryType.SERVICE


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (ConnectionRefusedError, ConfigEntryState.SETUP_RETRY),
        (OpenRGBDisconnected, ConfigEntryState.SETUP_RETRY),
        (ControllerParsingError, ConfigEntryState.SETUP_RETRY),
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
        (socket.gaierror, ConfigEntryState.SETUP_RETRY),
        (SDKVersionError, ConfigEntryState.SETUP_RETRY),
        (RuntimeError("Test error"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup entry with various exceptions."""
    mock_config_entry.add_to_hass(hass)

    mock_openrgb_client.client_class_mock.side_effect = exception

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is expected_state
