"""Test for the switchbot_cloud image."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from switchbot_api import Device

from homeassistant.components.switchbot_cloud.image import SwitchBotCloudImage
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import configure_integration

TEST_IMAGE_URL = "https://test.s3.amazonaws.com/test.jpg"
TEST_IMAGE_CONTENT = b"fake_jpeg_data"


@pytest.fixture
def mock_api():
    """Fixture for mock SwitchBotAPI."""
    return Mock(name="SwitchBotAPI")


@pytest.fixture
def mock_device():
    """Fixture for mock Device/Remote."""
    return Mock(name="Device", device_id="test_device_123")


@pytest.fixture
def mock_coordinator():
    """Fixture for mock SwitchBotCoordinator."""
    coordinator = Mock(name="SwitchBotCoordinator")
    coordinator.hass = Mock(name="HASS")
    coordinator.data = None
    return coordinator


@pytest.fixture
def image_entity(mock_api, mock_device, mock_coordinator):
    """Fixture for SwitchBotCloudImage entity."""
    return SwitchBotCloudImage(
        api=mock_api, device=mock_device, coordinator=mock_coordinator
    )


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


@pytest.mark.asyncio
async def test_async_image(image_entity, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test async_image method triggers download and returns content."""
    mock_download = AsyncMock(return_value=None)
    monkeypatch.setattr(image_entity, "download_image", mock_download)
    result = await image_entity.async_image()
    mock_download.assert_awaited_once()
    assert result == image_entity._image_content


@pytest.mark.asyncio
async def test_download_image_empty_url(image_entity) -> None:
    """Test download_image with empty/invalid URL."""
    image_entity._attr_image_url = ""
    await image_entity.download_image()
    assert image_entity._image_content == b""

    image_entity._attr_image_url = None
    await image_entity.download_image()
    assert image_entity._image_content == b""


@pytest.mark.asyncio
async def test_async_update(image_entity) -> None:
    """Test async_update method updates image_last_updated."""
    before_update = datetime.now()
    await image_entity.async_update()
    assert image_entity._attr_image_last_updated > before_update
