"""Test Hikvision cameras."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import async_get_image
from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import TEST_DEVICE_ID, TEST_DEVICE_NAME, TEST_HOST, TEST_PASSWORD

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.CAMERA]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all camera entities."""
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_camera_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test camera entity is created."""
    await setup_integration(hass, mock_config_entry)

    # Check camera entity exists
    state = hass.states.get("camera.front_camera")
    assert state is not None
    assert state.state == "idle"


async def test_camera_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test camera is linked to device."""
    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_DEVICE_ID)}
    )
    assert device_entry is not None
    assert device_entry.name == TEST_DEVICE_NAME
    assert device_entry.manufacturer == "Hikvision"
    assert device_entry.model == "Camera"


async def test_camera_nvr_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test camera naming for NVR devices with multiple channels."""
    mock_hikcamera.return_value.get_type = "NVR"
    mock_hikcamera.return_value.get_channels.return_value = [1, 2]

    await setup_integration(hass, mock_config_entry)

    # NVR cameras should have channel number in name
    state = hass.states.get("camera.front_camera_channel_1")
    assert state is not None

    state = hass.states.get("camera.front_camera_channel_2")
    assert state is not None


async def test_camera_no_channels_creates_single_camera(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test camera created when device returns no channels."""
    mock_hikcamera.return_value.get_channels.return_value = []

    await setup_integration(hass, mock_config_entry)

    # Single camera should be created for channel 1
    states = hass.states.async_entity_ids("camera")
    assert len(states) == 1

    state = hass.states.get("camera.front_camera")
    assert state is not None


async def test_camera_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test getting camera image."""
    await setup_integration(hass, mock_config_entry)

    image = await async_get_image(hass, "camera.front_camera")
    assert image.content == b"fake_image_data"

    # Verify get_snapshot was called with channel 1
    mock_hikcamera.return_value.get_snapshot.assert_called_with(1)


async def test_camera_image_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test camera image error handling."""
    mock_hikcamera.return_value.get_snapshot.side_effect = Exception("Connection error")

    await setup_integration(hass, mock_config_entry)

    camera_entity = hass.data["camera"].get_entity("camera.front_camera")
    result = await camera_entity.async_camera_image()
    assert result is None
    assert "Error getting camera image" in caplog.text


async def test_camera_stream_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test camera stream source URL."""
    await setup_integration(hass, mock_config_entry)

    camera_entity = hass.data["camera"].get_entity("camera.front_camera")
    stream_url = await camera_entity.stream_source()

    # Verify RTSP URL from library
    assert stream_url is not None
    assert stream_url.startswith("rtsp://")
    assert f"@{TEST_HOST}:554/Streaming/Channels/1" in stream_url

    # Verify get_stream_url was called with channel 1
    mock_hikcamera.return_value.get_stream_url.assert_called_with(1)


async def test_camera_stream_source_nvr(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test NVR camera stream source URL."""
    mock_hikcamera.return_value.get_type = "NVR"
    mock_hikcamera.return_value.get_channels.return_value = [2]
    mock_hikcamera.return_value.get_stream_url.return_value = (
        f"rtsp://admin:{TEST_PASSWORD}@{TEST_HOST}:554/Streaming/Channels/201"
    )

    await setup_integration(hass, mock_config_entry)

    camera_entity = hass.data["camera"].get_entity("camera.front_camera_channel_2")
    stream_url = await camera_entity.stream_source()

    # NVR channel 2 should use stream channel 201
    assert stream_url is not None
    assert f"@{TEST_HOST}:554/Streaming/Channels/201" in stream_url

    # Verify get_stream_url was called with channel 2
    mock_hikcamera.return_value.get_stream_url.assert_called_with(2)
