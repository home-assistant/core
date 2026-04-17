"""Test the Hisense ConnectLife coordinator."""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hisense_connectlife.coordinator import (
    HisenseACPluginDataUpdateCoordinator,
)
from homeassistant.components.hisense_connectlife.models import DeviceInfo
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.loop = MagicMock()
    hass.loop.call_soon_threadsafe = MagicMock()
    return hass


@pytest.mark.asyncio
async def test_async_setup_success(
    mock_hass, mock_config_entry, mock_api_client
) -> None:
    """Test successful async_setup."""
    device = DeviceInfo(
        {
            "deviceId": "test_device_1",
            "puid": "test_puid_1",
            "deviceTypeCode": "009",
            "deviceFeatureCode": "199",
            "statusList": {"t_power": "1"},
        }
    )
    devices = {device.device_id: device}
    mock_api_client.async_get_devices = AsyncMock(return_value=devices)
    mock_api_client.async_setup_websocket = AsyncMock()

    coordinator = HisenseACPluginDataUpdateCoordinator(
        mock_hass, mock_api_client, mock_config_entry
    )

    result = await coordinator.async_setup()

    assert result is True
    mock_api_client.async_setup_websocket.assert_awaited_once_with(
        coordinator._handle_ws_message
    )
    assert coordinator.data == devices
    assert coordinator._devices == devices


@pytest.mark.asyncio
async def test_async_setup_returns_false_when_no_devices(
    mock_hass, mock_config_entry, mock_api_client
) -> None:
    """Test async_setup returns False when no devices are found."""
    mock_api_client.async_get_devices = AsyncMock(return_value={})
    mock_api_client.async_setup_websocket = AsyncMock()

    coordinator = HisenseACPluginDataUpdateCoordinator(
        mock_hass, mock_api_client, mock_config_entry
    )

    result = await coordinator.async_setup()

    assert result is False
    mock_api_client.async_setup_websocket.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_update_data_success(
    mock_hass, mock_config_entry, mock_api_client
) -> None:
    """Test successful _async_update_data."""
    device = DeviceInfo(
        {
            "deviceId": "test_device_1",
            "puid": "test_puid_1",
            "deviceTypeCode": "009",
            "deviceFeatureCode": "199",
            "statusList": {"t_power": "1"},
        }
    )
    devices = {device.device_id: device}
    mock_api_client.async_get_devices = AsyncMock(return_value=devices)

    coordinator = HisenseACPluginDataUpdateCoordinator(
        mock_hass, mock_api_client, mock_config_entry
    )

    result = await coordinator._async_update_data()

    assert result == devices
    assert coordinator.data == devices
    assert coordinator._devices == devices


@pytest.mark.asyncio
async def test_async_update_data_fails_when_no_devices(
    mock_hass, mock_config_entry, mock_api_client
) -> None:
    """Test _async_update_data raises UpdateFailed when no devices are found."""
    mock_api_client.async_get_devices = AsyncMock(return_value={})

    coordinator = HisenseACPluginDataUpdateCoordinator(
        mock_hass, mock_api_client, mock_config_entry
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


def test_get_device_by_device_id_and_puid(
    mock_hass, mock_config_entry, mock_api_client
) -> None:
    """Test get_device can find device by both device_id and puid."""
    device = DeviceInfo(
        {
            "deviceId": "test_device_1",
            "puid": "test_puid_1",
            "deviceTypeCode": "009",
            "deviceFeatureCode": "199",
            "statusList": {"t_power": "1"},
        }
    )
    coordinator = HisenseACPluginDataUpdateCoordinator(
        mock_hass, mock_api_client, mock_config_entry
    )
    coordinator._devices = {device.device_id: device}

    assert coordinator.get_device(device.device_id) == device
    assert coordinator.get_device(device.puid) == device


def test_parse_content_invalid(mock_hass, mock_config_entry, mock_api_client) -> None:
    """Test _parse_content returns None for invalid content."""
    coordinator = HisenseACPluginDataUpdateCoordinator(
        mock_hass, mock_api_client, mock_config_entry
    )

    assert coordinator._parse_content({"content": {"not": "a string"}}) is None
    assert coordinator._parse_content({"content": "not-json"}) is None


def test_update_wifi_status_sets_offline_state(
    mock_hass, mock_config_entry, mock_api_client
) -> None:
    """Test _update_wifi_status sets offlineState based on onlinestats."""
    coordinator = HisenseACPluginDataUpdateCoordinator(
        mock_hass, mock_api_client, mock_config_entry
    )
    device_data = {"statusList": {}}

    coordinator._update_wifi_status(device_data, {"onlinestats": "1"})
    assert device_data["offlineState"] == 0

    coordinator._update_wifi_status(device_data, {"onlinestats": "0"})
    assert device_data["offlineState"] == 1


def test_update_device_status_decodes_base64_and_properties(
    mock_hass, mock_config_entry, mock_api_client
) -> None:
    """Test _update_device_status decodes base64 status and merges properties."""
    coordinator = HisenseACPluginDataUpdateCoordinator(
        mock_hass, mock_api_client, mock_config_entry
    )
    payload = {"t_temp": "23"}
    status = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    device_data = {"statusList": {"t_power": "0"}}

    coordinator._update_device_status(
        device_data,
        {
            "status": status,
            "properties": {"t_work_mode": "cool"},
        },
    )

    assert device_data["statusList"]["t_temp"] == "23"
    assert device_data["statusList"]["t_power"] == "0"
    assert device_data["statusList"]["t_work_mode"] == "cool"


@patch(
    "homeassistant.components.hisense_connectlife.coordinator.get_device_parser",
    return_value=MagicMock(),
)
def test_notify_update_calls_async_set_updated_data(
    mock_get_device_parser, mock_hass, mock_config_entry, mock_api_client
) -> None:
    """Test _notify_update calls async_set_updated_data with current devices."""
    coordinator = HisenseACPluginDataUpdateCoordinator(
        mock_hass, mock_api_client, mock_config_entry
    )
    device = DeviceInfo(
        {
            "deviceId": "test_device_1",
            "puid": "test_puid_1",
            "deviceTypeCode": "009",
            "deviceFeatureCode": "199",
            "statusList": {"t_power": "1"},
        }
    )
    coordinator._devices = {device.device_id: device}
    coordinator.async_set_updated_data = MagicMock()

    coordinator._notify_update()

    mock_get_device_parser.assert_called_once()
    mock_hass.loop.call_soon_threadsafe.assert_called_once_with(
        coordinator.async_set_updated_data, coordinator._devices
    )


@pytest.mark.asyncio
async def test_handle_ws_message_triggers_notify_update(
    mock_hass, mock_config_entry, mock_api_client
) -> None:
    """Test _handle_ws_message triggers _notify_update and updates device status."""
    device = DeviceInfo(
        {
            "deviceId": "test_device_1",
            "puid": "test_puid_1",
            "deviceTypeCode": "009",
            "deviceFeatureCode": "199",
            "statusList": {"t_power": "1"},
        }
    )
    coordinator = HisenseACPluginDataUpdateCoordinator(
        mock_hass, mock_api_client, mock_config_entry
    )
    coordinator._devices = {device.device_id: device}
    coordinator.async_set_updated_data = MagicMock()

    message = {
        "msgTypeCode": "status_wifistatus",
        "content": json.dumps({"puid": device.puid, "onlinestats": "1"}),
    }

    with patch(
        "homeassistant.components.hisense_connectlife.coordinator.get_device_parser",
        return_value=MagicMock(),
    ):
        coordinator._handle_ws_message(message)

    assert mock_hass.loop.call_soon_threadsafe.called
    assert coordinator._devices[device.device_id].offline_state == 0


@pytest.mark.asyncio
async def test_async_control_device_raises_update_failed(
    mock_hass, mock_config_entry, mock_api_client
) -> None:
    """Test async_control_device raises UpdateFailed on API error."""
    mock_api_client.async_control_device = AsyncMock(side_effect=Exception("boom"))
    coordinator = HisenseACPluginDataUpdateCoordinator(
        mock_hass, mock_api_client, mock_config_entry
    )

    with pytest.raises(UpdateFailed):
        await coordinator.async_control_device("test_puid_1", {"t_power": "0"})


@pytest.mark.asyncio
async def test_async_refresh_device_does_not_call_api_for_unknown_device(
    mock_hass, mock_config_entry, mock_api_client
) -> None:
    """Test async_refresh_device does not call API for unknown device."""
    mock_api_client.async_get_devices = AsyncMock()
    coordinator = HisenseACPluginDataUpdateCoordinator(
        mock_hass, mock_api_client, mock_config_entry
    )

    await coordinator.async_refresh_device("missing")

    mock_api_client.async_get_devices.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_refresh_device_updates_known_device(
    mock_hass, mock_config_entry, mock_api_client
) -> None:
    """Test async_refresh_device updates status of known device."""
    old_device = DeviceInfo(
        {
            "deviceId": "test_device_1",
            "puid": "test_puid_1",
            "deviceTypeCode": "009",
            "deviceFeatureCode": "199",
            "statusList": {"t_power": "0"},
        }
    )
    updated_device = DeviceInfo(
        {
            "deviceId": "test_device_1",
            "puid": "test_puid_1",
            "deviceTypeCode": "009",
            "deviceFeatureCode": "199",
            "statusList": {"t_power": "1"},
        }
    )
    coordinator = HisenseACPluginDataUpdateCoordinator(
        mock_hass, mock_api_client, mock_config_entry
    )
    coordinator._devices = {old_device.device_id: old_device}
    coordinator.async_set_updated_data = MagicMock()
    mock_api_client.async_get_devices = AsyncMock(
        return_value={updated_device.device_id: updated_device}
    )

    await coordinator.async_refresh_device(old_device.device_id)

    assert coordinator._devices[old_device.device_id].status["t_power"] == "1"
    coordinator.async_set_updated_data.assert_called_once_with(coordinator._devices)


@pytest.mark.asyncio
async def test_async_refresh_all_devices_updates_data(
    mock_hass, mock_config_entry, mock_api_client
) -> None:
    """Test async_refresh_all_devices fetches devices and updates data."""
    device = DeviceInfo(
        {
            "deviceId": "test_device_1",
            "puid": "test_puid_1",
            "deviceTypeCode": "009",
            "deviceFeatureCode": "199",
            "statusList": {"t_power": "1"},
        }
    )
    devices = {device.device_id: device}
    coordinator = HisenseACPluginDataUpdateCoordinator(
        mock_hass, mock_api_client, mock_config_entry
    )
    coordinator.async_set_updated_data = MagicMock()
    mock_api_client.async_get_devices = AsyncMock(return_value=devices)

    await coordinator.async_refresh_all_devices()

    assert coordinator._devices == devices
    assert coordinator.data == devices
    coordinator.async_set_updated_data.assert_called_once_with(devices)


@pytest.mark.asyncio
async def test_async_unload_calls_cleanup(
    mock_hass, mock_config_entry, mock_api_client
) -> None:
    """Test async_unload calls API client's async_cleanup."""
    mock_api_client.async_cleanup = AsyncMock()
    coordinator = HisenseACPluginDataUpdateCoordinator(
        mock_hass, mock_api_client, mock_config_entry
    )

    await coordinator.async_unload()

    mock_api_client.async_cleanup.assert_awaited_once()
