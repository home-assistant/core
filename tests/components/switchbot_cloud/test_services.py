"""Tests for switchbot_cloud service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from switchbot_api import Device

from homeassistant.components.switchbot_cloud import (
    AI_ART_FRAME_UPLOAD_IMAGE_SERVICE,
    DOMAIN,
)
from homeassistant.components.switchbot_cloud.service import async_register_services
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
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
    entry = await _setup(hass, mock_list_devices, mock_get_status, mock_setup_webhook)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "AABBCCDDEEFF")},
        name="test-art-frame",
        model="AI Art Frame",
    )
    with patch.object(
        entry.runtime_data.api, "send_command", new_callable=AsyncMock
    ) as mock_send:
        await hass.services.async_call(
            DOMAIN,
            AI_ART_FRAME_UPLOAD_IMAGE_SERVICE,
            {"device_id": device.id, "image_url": "https://example.com/img.jpg"},
            blocking=True,
        )
    mock_send.assert_awaited_once_with(
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
    await _setup(hass, mock_list_devices, mock_get_status, mock_setup_webhook)
    with pytest.raises(ServiceValidationError, match="Target Device ID is required"):
        await hass.services.async_call(
            DOMAIN,
            AI_ART_FRAME_UPLOAD_IMAGE_SERVICE,
            {"image_url": "https://example.com/img.jpg"},
            blocking=True,
        )


async def test_upload_image_wrong_model_skips(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_list_devices,
    mock_get_status,
) -> None:
    """Test service skips devices that are not AI Art Frame."""
    hub = Device(
        version="V1.0",
        deviceId="FFEEDDCCBBAA",
        deviceName="test-hub",
        deviceType="Hub Mini",
        hubDeviceId="test-hub-id",
    )
    entry = await _setup(hass, mock_list_devices, mock_get_status, device=hub)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "FFEEDDCCBBAA")},
        name="test-hub",
        model="Hub Mini",
    )
    with patch.object(
        entry.runtime_data.api, "send_command", new_callable=AsyncMock
    ) as mock_send:
        await hass.services.async_call(
            DOMAIN,
            AI_ART_FRAME_UPLOAD_IMAGE_SERVICE,
            {"device_id": device.id, "image_url": "https://example.com/img.jpg"},
            blocking=True,
        )
    mock_send.assert_not_awaited()


async def test_no_entries_raises(hass: HomeAssistant) -> None:
    """Test service raises when switchbot_cloud has no config entries."""

    async_register_services(hass)
    with pytest.raises(
        ServiceValidationError, match="switchbot_cloud is not configured"
    ):
        await hass.services.async_call(
            DOMAIN,
            AI_ART_FRAME_UPLOAD_IMAGE_SERVICE,
            {"device_id": "some-id", "image_url": "https://example.com/img.jpg"},
            blocking=True,
        )


async def test_device_not_in_registry_skips(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_setup_webhook,
) -> None:
    """Test service skips when device_id is not found in device registry."""
    entry = await _setup(hass, mock_list_devices, mock_get_status, mock_setup_webhook)
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


async def test_entry_not_matched_raises(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_list_devices,
    mock_get_status,
    mock_setup_webhook,
) -> None:
    """Test service raises when device entry_id matches no loaded entry."""
    entry = await _setup(hass, mock_list_devices, mock_get_status, mock_setup_webhook)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "AABBCCDDEEFF")},
        name="test-art-frame",
        model="AI Art Frame",
    )
    other_entry = MagicMock()
    other_entry.entry_id = "other-entry-id"
    with (
        patch.object(hass.config_entries, "async_entries", return_value=[other_entry]),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            AI_ART_FRAME_UPLOAD_IMAGE_SERVICE,
            {"device_id": device.id, "image_url": "https://example.com/img.jpg"},
            blocking=True,
        )
