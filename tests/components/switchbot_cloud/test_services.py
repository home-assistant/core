"""Tests for switchbot_cloud service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from switchbot_api import Device, SwitchBotAPI
import voluptuous as vol

from homeassistant.components.switchbot_cloud import SwitchbotDevices
from homeassistant.components.switchbot_cloud.const import (
    AI_ART_FRAME_UPLOAD_IMAGE_SERVICE,
    DISABLE_DEVICE_WEBHOOK_SERVICE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import AI_ART_FRAME_DEVICE, configure_integration


async def _setup(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    device=AI_ART_FRAME_DEVICE,
):
    """Load default entry."""
    mock_list_devices.return_value = [device]
    mock_get_status.return_value = None
    with patch("homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.SWITCH]):
        entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    return entry


async def test_upload_image_success(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_list_devices,
    mock_get_status,
    mock_setup_webhook,
) -> None:
    """Test successful image upload to AI Art Frame."""
    entry = await _setup(hass, mock_list_devices, mock_get_status)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "AABBCCDDEEFF")},
        name="test-art-frame",
        model="AI Art Frame",
    )
    with (
        patch.object(SwitchBotAPI, "send_command") as mock_send_command,
    ):
        await hass.services.async_call(
            DOMAIN,
            AI_ART_FRAME_UPLOAD_IMAGE_SERVICE,
            {"device_id": device.id, "image_url": "https://example.com/img.jpg"},
            blocking=True,
        )
    mock_send_command.assert_awaited_once_with(
        device_id="AABBCCDDEEFF",
        command="uploadImage",
        command_type="command",
        parameters={"imageUrl": "https://example.com/img.jpg"},
    )


async def test_upload_image_no_device_id_raises(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_setup_webhook,
) -> None:
    """Test service raises when no device_id is provided."""
    await _setup(hass, mock_list_devices, mock_get_status)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            AI_ART_FRAME_UPLOAD_IMAGE_SERVICE,
            {"image_url": "https://example.com/img.jpg"},
            blocking=True,
        )


async def test_device_not_in_registry_skips(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_setup_webhook,
) -> None:
    """Test service skips when device_id is not found in device registry."""
    entry = await _setup(hass, mock_list_devices, mock_get_status)
    with patch.object(
        entry.runtime_data.api, "send_command", new_callable=AsyncMock
    ) as mock_send:
        await hass.services.async_call(
            DOMAIN,
            AI_ART_FRAME_UPLOAD_IMAGE_SERVICE,
            {
                "device_id": "nonexistent-device-id",
                "image_url": "https://example.com/img.jpg",
            },
            blocking=True,
        )
    mock_send.assert_not_awaited()


async def test_device_without_mac_raises_service_validation_error(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_list_devices,
    mock_get_status,
    mock_setup_webhook,
) -> None:
    """Test service device without mac."""
    entry = await _setup(hass, mock_list_devices, mock_get_status)

    device_no_mac = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("other_integration", "some-id")},
        name="no-mac-device",
    )

    with pytest.raises(ServiceValidationError, match="No valid MAC address obtained"):
        await hass.services.async_call(
            DOMAIN,
            AI_ART_FRAME_UPLOAD_IMAGE_SERVICE,
            {
                "device_id": [device_no_mac.id],
                "image_url": "https://example.com/img.jpg",
            },
            blocking=True,
        )


async def test_disable_webhook_success(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_list_devices,
    mock_get_status,
    mock_setup_webhook,
) -> None:
    """Test disable_webhook is called on the matching coordinator."""
    entry = await _setup(hass, mock_list_devices, mock_get_status)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "AABBCCDDEEFF")},
        name="meter-1",
        model="Meter",
    )

    mock_device_info = Device(
        version="V1.0",
        deviceId="AABBCCDDEEFF",
        deviceName="meter-1",
        deviceType="Meter",
        hubDeviceId="test-hub-id",
    )

    mock_coord = MagicMock()
    mock_coord.disable_webhook.return_value = None

    fake_devices = SwitchbotDevices(sensors=[(mock_device_info, mock_coord)])
    with patch.object(entry.runtime_data, "devices", fake_devices):
        await hass.services.async_call(
            DOMAIN,
            DISABLE_DEVICE_WEBHOOK_SERVICE,
            {"device_id": [device.id]},
            blocking=True,
        )
    mock_coord.disable_webhook.assert_called_once()


async def test_disable_webhook_device_not_in_registry_skips(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_list_devices,
    mock_get_status,
    mock_setup_webhook,
) -> None:
    """Test service skips silently when device_id is not found in device registry."""
    entry = await _setup(hass, mock_list_devices, mock_get_status)

    mock_coord = MagicMock()
    mock_coord.disable_webhook.return_value = None

    fake_devices = SwitchbotDevices(sensors=[])
    with patch.object(entry.runtime_data, "devices", fake_devices):
        await hass.services.async_call(
            DOMAIN,
            DISABLE_DEVICE_WEBHOOK_SERVICE,
            {"device_id": ["nonexistent-device-id"]},
            blocking=True,
        )
    mock_coord.disable_webhook.assert_not_called()


async def test_disable_webhook_no_device_id_raises(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_setup_webhook,
) -> None:
    """Test schema raises when no device_id is provided."""
    await _setup(hass, mock_list_devices, mock_get_status)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            DISABLE_DEVICE_WEBHOOK_SERVICE,
            {},
            blocking=True,
        )


async def test_disable_webhook_device_without_mac_raises(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_list_devices,
    mock_get_status,
    mock_setup_webhook,
) -> None:
    """Test service raises ServiceValidationError when device has no DOMAIN MAC."""
    entry = await _setup(hass, mock_list_devices, mock_get_status)
    device_no_mac = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("other_integration", "some-id")},
        name="no-mac-device",
    )
    with pytest.raises(ServiceValidationError, match="No valid MAC address obtained"):
        await hass.services.async_call(
            DOMAIN,
            DISABLE_DEVICE_WEBHOOK_SERVICE,
            {"device_id": [device_no_mac.id]},
            blocking=True,
        )
