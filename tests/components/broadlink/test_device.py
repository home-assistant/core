"""Tests for Broadlink devices."""
import broadlink.exceptions as blke

from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_SETUP_ERROR,
    ENTRY_STATE_SETUP_RETRY,
)

from . import pick_device

from tests.async_mock import AsyncMock, MagicMock, patch


async def test_device_setup(hass):
    """Test a successful setup."""
    device = pick_device(1)
    mock_api = device.get_mock_api()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward:
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_LOADED
    assert mock_api.auth.call_count == 1
    assert mock_api.get_fwversion.call_count == 1
    assert len(mock_forward.mock_calls) == 3
    forward_entries = {c[1][1] for c in mock_forward.mock_calls}
    assert forward_entries == {"remote", "sensor", "switch"}


async def test_device_setup_authentication_error(hass):
    """Test we handle an authentication error."""
    device = pick_device(1)
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.AuthenticationError()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward, patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init:
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_SETUP_ERROR
    assert len(mock_forward.mock_calls) == 0
    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][2]["context"]["source"] == "reauth"
    assert mock_init.mock_calls[0][2]["data"] == {
        "name": device.name,
        **device.get_entry_data(),
    }


async def test_device_setup_device_offline(hass):
    """Test we handle a device offline."""
    device = pick_device(1)
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.DeviceOfflineError()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api):
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_SETUP_RETRY


async def test_device_setup_os_error(hass):
    """Test we handle an OS error."""
    device = pick_device(1)
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = OSError()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api):
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_SETUP_RETRY


async def test_device_setup_update_failed(hass):
    """Test we handle an update failure at startup."""
    device = pick_device(1)
    mock_api = device.get_mock_api()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    mock_update_manager = MagicMock()
    mock_update_manager.coordinator.last_update_success = False
    mock_update_manager.coordinator.async_refresh = AsyncMock()

    with patch("broadlink.gendevice", return_value=mock_api), patch(
        "homeassistant.components.broadlink.device.get_update_manager",
        return_value=mock_update_manager,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_SETUP_RETRY
