"""Tests for Broadlink devices."""
import broadlink.exceptions as blke
import pytest

from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.broadlink.device import BroadlinkDevice
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component

from . import pick_device

from tests.async_mock import patch


async def test_device_setup(hass):
    """Test a successful setup."""
    device = pick_device(1)
    mock_api = device.get_mock_api()
    mock_entry = device.get_mock_entry()
    device_entry = BroadlinkDevice(hass, mock_entry)
    await async_setup_component(hass, DOMAIN, {})

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward:
        assert await device_entry.async_setup() is True

    assert device_entry.api is mock_api
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
    device_entry = BroadlinkDevice(hass, mock_entry)
    await async_setup_component(hass, DOMAIN, {})

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward, patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init:
        assert await device_entry.async_setup() is False

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
    device_entry = BroadlinkDevice(hass, mock_entry)
    await async_setup_component(hass, DOMAIN, {})

    with patch("broadlink.gendevice", return_value=mock_api), pytest.raises(
        ConfigEntryNotReady
    ):
        await device_entry.async_setup()


async def test_device_setup_os_error(hass):
    """Test we handle an OS error."""
    device = pick_device(1)
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = OSError()
    mock_entry = device.get_mock_entry()
    device_entry = BroadlinkDevice(hass, mock_entry)
    await async_setup_component(hass, DOMAIN, {})

    with patch("broadlink.gendevice", return_value=mock_api), pytest.raises(
        ConfigEntryNotReady
    ):
        await device_entry.async_setup()
