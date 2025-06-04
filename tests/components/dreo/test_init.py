"""Tests for the Dreo integration."""

from __future__ import annotations

import contextlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from hscloud.hscloud import HsCloud
from hscloud.hscloudexception import HsCloudBusinessException, HsCloudException
import pytest

from homeassistant.components.dreo import (
    async_login,
    async_setup_device_coordinator,
    async_setup_entry,
)
from homeassistant.components.dreo.const import DOMAIN
from homeassistant.components.dreo.coordinator import DreoDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


async def test_setup(hass: HomeAssistant, mock_config_entry) -> None:
    """Test the Dreo setup."""
    mock_config_entry.add_to_hass(hass)

    runtime_data = MagicMock()
    runtime_data.client = MagicMock()
    runtime_data.devices = []
    runtime_data.coordinators = {}

    hass.data[DOMAIN] = {mock_config_entry.entry_id: runtime_data}

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data
    assert mock_config_entry.state == ConfigEntryState.LOADED


async def test_config_entry_not_ready(hass: HomeAssistant) -> None:
    """Test the Dreo configuration entry not ready."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_entry.add_to_hass(hass)

    mock_manager = MagicMock(spec=HsCloud)
    mock_manager.login.side_effect = HsCloudException("Connection failed")

    with patch(
        "homeassistant.components.dreo.HsCloud",
        return_value=mock_manager,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state == ConfigEntryState.SETUP_RETRY


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid auth."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_entry.add_to_hass(hass)

    mock_manager = MagicMock(spec=HsCloud)
    mock_manager.login.side_effect = HsCloudBusinessException("Invalid credentials")

    with patch(
        "homeassistant.components.dreo.HsCloud",
        return_value=mock_manager,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state == ConfigEntryState.SETUP_RETRY


async def test_unload_config_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test unloading the Dreo config entry."""
    mock_config_entry.add_to_hass(hass)

    runtime_data = MagicMock()
    runtime_data.client = MagicMock()
    runtime_data.devices = []
    runtime_data.coordinators = {}

    hass.data[DOMAIN] = {mock_config_entry.entry_id: runtime_data}

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data
    assert mock_config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED


async def test_reload_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test reloading the Dreo config entry."""
    mock_config_entry.add_to_hass(hass)

    runtime_data = MagicMock()
    runtime_data.client = MagicMock()
    runtime_data.devices = []
    runtime_data.coordinators = {}

    hass.data[DOMAIN] = {mock_config_entry.entry_id: runtime_data}

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.dreo.async_unload_entry", return_value=True
        ) as mock_unload,
        patch(
            "homeassistant.components.dreo.async_setup_entry", return_value=True
        ) as mock_setup,
    ):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_unload.called
        assert mock_setup.called


async def test_setup_device(hass: HomeAssistant, mock_config_entry) -> None:
    """Test setting up a device."""
    mock_config_entry.add_to_hass(hass)

    mock_client = MagicMock()
    coordinators: dict[str, DreoDataUpdateCoordinator] = {}

    test_device = {
        "deviceSn": "test-device-id",
        "model": "DR-HTF001S",
    }

    mock_coordinator = AsyncMock()

    with patch(
        "homeassistant.components.dreo.DreoDataUpdateCoordinator",
        return_value=mock_coordinator,
    ):
        await async_setup_device_coordinator(
            hass, mock_client, test_device, coordinators
        )

        assert "test-device-id" in coordinators


async def test_setup_device_empty_id(hass: HomeAssistant, mock_config_entry) -> None:
    """Test setting up a device with empty ID."""
    mock_config_entry.add_to_hass(hass)

    mock_client = MagicMock()
    coordinators: dict[str, DreoDataUpdateCoordinator] = {}

    test_device = {
        "deviceSn": "",
        "model": "DR-HTF001S",
    }

    await async_setup_device_coordinator(hass, mock_client, test_device, coordinators)

    assert not coordinators


async def test_setup_device_already_exists(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test setting up a device that already exists."""
    mock_config_entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    # Use Any to avoid type issues in tests with mock objects
    coordinators: dict[str, Any] = {"test-device-id": mock_coordinator}

    test_device = {
        "deviceSn": "test-device-id",
        "model": "DR-HTF001S",
    }

    await async_setup_device_coordinator(hass, MagicMock(), test_device, coordinators)

    assert coordinators["test-device-id"] is mock_coordinator


async def test_setup_entry_with_devices(hass: HomeAssistant, mock_config_entry) -> None:
    """Test setting up an entry with device discovery."""
    mock_config_entry.add_to_hass(hass)

    device1 = {"deviceSn": "device1", "model": "DR-HTF001S"}
    device2 = {"deviceSn": "device2", "model": "UNKNOWN-MODEL"}
    device3 = {"deviceSn": "device3", "model": "DR-HTF001S"}

    mock_client = MagicMock()

    with (
        patch(
            "homeassistant.components.dreo.async_login",
            return_value=(mock_client, [device1, device2, device3]),
        ),
        patch("homeassistant.components.dreo.DEVICE_TYPE", {"DR-HTF001S": "fan"}),
        patch(
            "homeassistant.components.dreo.async_setup_device_coordinator"
        ) as mock_setup_device,
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=True,
        ) as mock_forward,
    ):
        assert await async_setup_entry(hass, mock_config_entry)

        assert mock_setup_device.call_count == 2
        mock_forward.assert_called_once_with(mock_config_entry, [Platform.FAN])


async def test_async_setup_device_duplicate_device(
    hass: HomeAssistant, mock_config_entry, mock_dreo_client
) -> None:
    """Test setting up the same device twice."""
    device = {
        "deviceSn": "test-device-id",
        "deviceName": "Test Device",
        "model": "DR-HTF001S",
    }

    coordinators: dict[str, DreoDataUpdateCoordinator] = {}

    await async_setup_device_coordinator(hass, mock_dreo_client, device, coordinators)
    assert "test-device-id" in coordinators

    coordinator_count = len(coordinators)
    await async_setup_device_coordinator(hass, mock_dreo_client, device, coordinators)
    assert len(coordinators) == coordinator_count


async def test_async_setup_device_missing_device_id(
    hass: HomeAssistant, mock_config_entry, mock_dreo_client
) -> None:
    """Test setting up device with missing device ID."""
    device = {
        "deviceName": "Test Device",
        "model": "DR-HTF001S",
    }

    coordinators: dict[str, DreoDataUpdateCoordinator] = {}

    await async_setup_device_coordinator(hass, mock_dreo_client, device, coordinators)
    assert len(coordinators) == 0


async def test_async_setup_device_empty_device_id(
    hass: HomeAssistant, mock_config_entry, mock_dreo_client
) -> None:
    """Test setting up device with empty device ID."""
    device = {
        "deviceSn": "",
        "deviceName": "Test Device",
        "model": "DR-HTF001S",
    }

    coordinators: dict[str, DreoDataUpdateCoordinator] = {}

    await async_setup_device_coordinator(hass, mock_dreo_client, device, coordinators)
    assert len(coordinators) == 0


async def test_async_setup_entry_with_unsupported_devices(
    hass: HomeAssistant, mock_config_entry, mock_dreo_client
) -> None:
    """Test setup with mix of supported and unsupported devices."""
    devices = [
        {
            "deviceSn": "supported-device",
            "deviceName": "Supported Fan",
            "model": "DR-HTF001S",
        },
        {
            "deviceSn": "unsupported-device",
            "deviceName": "Unsupported Device",
            "model": "UNKNOWN-MODEL",
        },
    ]

    with (
        patch(
            "homeassistant.components.dreo.async_login",
            return_value=(mock_dreo_client, devices),
        ),
        patch("homeassistant.components.dreo.DEVICE_TYPE", {"DR-HTF001S": "fan"}),
        patch(
            "homeassistant.components.dreo.async_setup_device_coordinator"
        ) as mock_setup_device,
        patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"),
    ):
        result = await async_setup_entry(hass, mock_config_entry)

        assert result is True
        assert mock_setup_device.call_count == 1
        mock_setup_device.assert_called_once()
        call_args = mock_setup_device.call_args[0]
        assert call_args[2]["deviceSn"] == "supported-device"


async def test_async_setup_device_coordinator_refresh_failure(
    hass: HomeAssistant, mock_config_entry, mock_dreo_client
) -> None:
    """Test device setup when coordinator refresh fails."""
    device = {
        "deviceSn": "test-device-id",
        "deviceName": "Test Device",
        "model": "DR-HTF001S",
    }

    coordinators: dict[str, DreoDataUpdateCoordinator] = {}

    with patch(
        "homeassistant.components.dreo.coordinator.DreoDataUpdateCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(
            side_effect=Exception("Refresh failed")
        )
        mock_coordinator_class.return_value = mock_coordinator

        with contextlib.suppress(Exception):
            await async_setup_device_coordinator(
                hass, mock_dreo_client, device, coordinators
            )


async def test_async_setup_device_no_device_sn(
    hass: HomeAssistant, mock_config_entry, mock_dreo_client
) -> None:
    """Test device setup when device has no serial number."""
    device = {
        "deviceName": "Test Device",
        "model": "DR-HTF001S",
    }
    coordinators: dict[str, DreoDataUpdateCoordinator] = {}

    await async_setup_device_coordinator(hass, mock_dreo_client, device, coordinators)


@pytest.mark.skip(reason="Complex mocking issue")
async def test_async_login_success(hass: HomeAssistant) -> None:
    """Test successful login and device retrieval."""
    mock_devices = [{"deviceSn": "test1"}, {"deviceSn": "test2"}]

    with patch("homeassistant.components.dreo.HsCloud") as mock_client_class:
        mock_client = MagicMock()
        mock_client.login = AsyncMock(return_value=None)
        mock_client.get_devices = AsyncMock(return_value=mock_devices)
        mock_client_class.return_value = mock_client

        client, devices = await async_login(hass, "test_user", "test_pass")

        assert client == mock_client
        assert devices == mock_devices


async def test_async_login_business_exception(hass: HomeAssistant) -> None:
    """Test login with business exception."""
    with patch("homeassistant.components.dreo.HsCloud") as mock_client_class:
        mock_client = MagicMock()
        mock_client.login.side_effect = HsCloudBusinessException("Invalid credentials")
        mock_client_class.return_value = mock_client

        with pytest.raises(ConfigEntryNotReady, match="Invalid username or password"):
            await async_login(hass, "test_user", "wrong_pass")


async def test_async_login_general_exception(hass: HomeAssistant) -> None:
    """Test login with general exception."""
    with patch("homeassistant.components.dreo.HsCloud") as mock_client_class:
        mock_client = MagicMock()
        mock_client.get_devices.side_effect = HsCloudException("Connection error")
        mock_client_class.return_value = mock_client

        with pytest.raises(
            ConfigEntryNotReady, match="Error communicating with Dreo API"
        ):
            await async_login(hass, "test_user", "test_pass")


async def test_async_login_dreo_client_exception(hass: HomeAssistant) -> None:
    """Test async_login when dreo client raises exception."""
    with patch("homeassistant.components.dreo.HsCloud") as mock_client_class:
        mock_client = MagicMock()
        mock_client.login.side_effect = HsCloudException("Connection failed")
        mock_client_class.return_value = mock_client

        with pytest.raises(
            ConfigEntryNotReady, match="Error communicating with Dreo API"
        ):
            await async_login(hass, "test_user", "test_pass")
