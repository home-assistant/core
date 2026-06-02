"""Tests for Xthings Cloud camera platform."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import async_get_image
from homeassistant.const import (
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_device_by_id, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_cameras(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test camera entities are created correctly."""
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_camera_unavailable_when_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test camera shows unavailable when device is offline."""
    get_device_by_id(mock_api_client, "dev_camera_001")["online"] = False
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("camera.front_door_camera")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

async def test_camera_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test camera image fetching."""
    mock_api_client.async_get_snapshot.return_value = b"image_data"
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("camera.front_door_camera")
    assert state is not None

    image = await async_get_image(hass, "camera.front_door_camera")
    assert image.content == b"image_data"
    mock_api_client.async_get_snapshot.assert_called_once_with("https://example.com/snapshot.jpg")

async def test_updating_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    mock_websocket: AsyncMock,
) -> None:
    """Test updating state and fetching new snapshot."""
    mock_api_client.async_get_snapshot.return_value = b"new_image_data"
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, mock_config_entry)

    assert mock_websocket.call_args is not None

    mock_websocket.call_args[1]["on_device_status"](
        "dev_camera_001",
        {
            "snapshot_url": "https://example.com/new_snapshot.jpg",
        },
    )
    
    await hass.async_block_till_done()
    
    mock_api_client.async_get_snapshot.assert_called_with("https://example.com/new_snapshot.jpg")

async def test_webrtc_offer(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test WebRTC offer handling."""
    mock_api_client.async_get_camera_webrtc.return_value = {
        "region": "us-east-1",
        "channel_arn": "arn:aws:kinesisvideo:us-east-1:111111111111:channel/test/123",
        "viewer": {
            "AccessKeyId": "test",
            "SecretAccessKey": "test",
            "SessionToken": "test",
        },
    }
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("camera.front_door_camera")
    assert state is not None


