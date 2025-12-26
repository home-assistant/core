"""Test Hikvision cameras."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import async_get_image
from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import TEST_DEVICE_ID, TEST_DEVICE_NAME

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
    mock_hikcamera.return_value.current_event_states = {
        "Motion": [(True, 1), (False, 2)],
    }

    await setup_integration(hass, mock_config_entry)

    # NVR cameras should have channel number in name
    state = hass.states.get("camera.front_camera_channel_1")
    assert state is not None

    state = hass.states.get("camera.front_camera_channel_2")
    assert state is not None


async def test_camera_nvr_unique_channels(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test only unique channels create camera entities."""
    mock_hikcamera.return_value.get_type = "NVR"
    mock_hikcamera.return_value.current_event_states = {
        "Motion": [(True, 1), (False, 2)],
        "Line Crossing": [(False, 1), (False, 2)],
    }

    await setup_integration(hass, mock_config_entry)

    # Should only create 2 cameras (one per unique channel)
    states = hass.states.async_entity_ids("camera")
    assert len(states) == 2


async def test_camera_no_sensors_creates_single_camera(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test camera created when device has no sensors."""
    mock_hikcamera.return_value.current_event_states = None

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

    with patch(
        "homeassistant.components.hikvision.camera.get_async_client"
    ) as mock_client:
        mock_response = MagicMock()
        mock_response.content = b"fake_image_data"
        mock_response.raise_for_status = MagicMock()
        mock_client.return_value.get = AsyncMock(return_value=mock_response)

        image = await async_get_image(hass, "camera.front_camera")
        assert image.content == b"fake_image_data"


async def test_camera_image_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test camera image timeout handling."""
    await setup_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.hikvision.camera.get_async_client"
    ) as mock_client:
        mock_client.return_value.get = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        entity = hass.states.get("camera.front_camera")
        assert entity is not None

        # Get camera entity and call async_camera_image directly
        camera_entity = hass.data["camera"].get_entity("camera.front_camera")
        result = await camera_entity.async_camera_image()
        assert result is None
        assert "Timeout getting camera image" in caplog.text


async def test_camera_image_http_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test camera image HTTP error handling."""
    await setup_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.hikvision.camera.get_async_client"
    ) as mock_client:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=MagicMock()
        )
        mock_client.return_value.get = AsyncMock(return_value=mock_response)

        camera_entity = hass.data["camera"].get_entity("camera.front_camera")
        result = await camera_entity.async_camera_image()
        assert result is None
        assert "HTTP error getting camera image" in caplog.text


async def test_camera_stream_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test camera stream source URL."""
    await setup_integration(hass, mock_config_entry)

    camera_entity = hass.data["camera"].get_entity("camera.front_camera")
    stream_url = await camera_entity.stream_source()

    # Verify RTSP URL format
    assert stream_url is not None
    assert stream_url.startswith("rtsp://")
    assert "@192.168.1.100:554/Streaming/Channels/1" in stream_url


async def test_camera_stream_source_nvr(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test NVR camera stream source URL with channel encoding."""
    mock_hikcamera.return_value.get_type = "NVR"
    mock_hikcamera.return_value.current_event_states = {
        "Motion": [(True, 2)],  # Only channel 2
    }

    await setup_integration(hass, mock_config_entry)

    camera_entity = hass.data["camera"].get_entity("camera.front_camera_channel_2")
    stream_url = await camera_entity.stream_source()

    # NVR channel 2 should use stream channel 201 (2*100+1)
    assert stream_url is not None
    assert "@192.168.1.100:554/Streaming/Channels/201" in stream_url
