"""Test for the switchbot_cloud image."""

from unittest.mock import AsyncMock, patch

from switchbot_api import Device

from homeassistant.components.switchbot_cloud import DOMAIN
from homeassistant.components.switchbot_cloud.image import SwitchBotCloudImage
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_coordinator_data_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test coordinator data is none."""

    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="ai-art-frame-id-1",
            deviceName="ai-art-frame-1",
            deviceType="AI Art Frame",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [None, None]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "image.ai_art_frame_1_display"
    state = hass.states.get(entity_id)
    assert state.state is STATE_UNKNOWN


async def test_async_image(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test coordinator data is none."""

    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="ai-art-frame-id-1",
            deviceName="ai-art-frame-1",
            deviceType="AI Art Frame",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {
            "deviceId": "B0E9FEA5D7F0",
            "deviceType": "AI Art Frame",
            "hubDeviceId": "B0E9FEA5D7F0",
            "battery": 0,
            "displayMode": 1,
            "imageUrl": "https://p3.itc.cn/images01/20231215/2f2db37e221c4ad3af575254c7769ca1.jpeg",
            "version": "V0.0-0.5",
        }
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    cloud_data = hass.data[DOMAIN][entry.entry_id]
    device, coordinator = cloud_data.devices.images[0]
    image_entity = SwitchBotCloudImage(cloud_data.api, device, coordinator)

    # 1. load before refresh
    await image_entity.async_image()
    assert image_entity._image_content == b""

    # 2. load after refresh
    with patch(
        "homeassistant.components.switchbot_cloud.image.get_file_stream_from_cloud",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.return_value = b"this is a bytes"
        image_entity._attr_image_url = (
            "https://p3.itc.cn/images01/20231215/2f2db37e221c4ad3af575254c7769ca1.jpeg"
        )
        await image_entity.async_image()
        assert image_entity._image_content == mock_get.return_value
