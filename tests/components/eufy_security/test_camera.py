"""Test the Eufy Security camera platform."""

import logging
from unittest.mock import AsyncMock, MagicMock

from eufy_security import EufySecurityError, InvalidCredentialsError
import pytest

from homeassistant.components.camera import CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_camera_entity(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test camera entity is created."""
    # With _attr_name = None, entity uses device name only
    state = hass.states.get("camera.front_door_camera")
    assert state is not None
    assert state.state == "idle"

    # Check entity registry
    entry = entity_registry.async_get("camera.front_door_camera")
    assert entry is not None
    assert entry.unique_id == "T1234567890-camera"


async def test_camera_attributes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test camera entity attributes."""
    state = hass.states.get("camera.front_door_camera")
    assert state is not None

    attributes = state.attributes
    assert attributes["serial_number"] == "T1234567890"
    assert attributes["station_serial"] == "T0987654321"
    assert attributes["hardware_version"] == "2.2"
    assert attributes["software_version"] == "2.0.7.6"
    assert attributes["ip_address"] == "192.168.1.100"


async def test_camera_device_info(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test camera device info."""
    entry = entity_registry.async_get("camera.front_door_camera")
    assert entry is not None
    assert entry.device_id is not None

    # Check device registry
    device = device_registry.async_get(entry.device_id)
    assert device is not None
    assert device.manufacturer == "Eufy"
    assert device.model == "eufyCam 2"
    assert device.name == "Front Door Camera"


async def test_camera_stream_source_local_rtsp(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
) -> None:
    """Test camera stream source returns local RTSP when credentials are set."""
    # Set RTSP credentials
    mock_camera.rtsp_username = "admin"
    mock_camera.rtsp_password = "password123"

    state = hass.states.get("camera.front_door_camera")
    assert state is not None

    # Get the entity
    entity = hass.data["camera"].get_entity("camera.front_door_camera")
    assert entity is not None

    # Call stream_source - should return local RTSP
    stream_url = await entity.stream_source()
    assert stream_url == "rtsp://admin:password123@192.168.1.100:554/live0"


async def test_camera_stream_source_cloud_fallback(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
) -> None:
    """Test camera stream source falls back to cloud when no RTSP credentials."""
    # No RTSP credentials set
    mock_camera.rtsp_username = None
    mock_camera.rtsp_password = None
    mock_camera.async_start_stream = AsyncMock(
        return_value="rtsp://cloud.eufy.com/stream123"
    )

    entity = hass.data["camera"].get_entity("camera.front_door_camera")
    stream_url = await entity.stream_source()

    assert stream_url == "rtsp://cloud.eufy.com/stream123"
    mock_camera.async_start_stream.assert_called_once()


async def test_camera_will_remove_from_hass(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
) -> None:
    """Test camera cleanup when removed from Home Assistant."""
    entity = hass.data["camera"].get_entity("camera.front_door_camera")

    # Set a stream URL to simulate active stream
    entity._stream_url = "rtsp://stream.url"

    # Mock the camera's async_stop_stream
    mock_camera.async_stop_stream = AsyncMock()

    await entity.async_will_remove_from_hass()

    mock_camera.async_stop_stream.assert_called_once()
    assert entity._stream_url is None


async def test_camera_will_remove_stop_stream_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
) -> None:
    """Test camera cleanup handles stop stream error gracefully."""
    entity = hass.data["camera"].get_entity("camera.front_door_camera")
    entity._stream_url = "rtsp://stream.url"

    # Mock stop stream to fail
    mock_camera.async_stop_stream = AsyncMock(
        side_effect=EufySecurityError("Stop failed")
    )

    # Should not raise
    await entity.async_will_remove_from_hass()
    assert entity._stream_url is None


async def test_camera_availability(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
) -> None:
    """Test camera availability based on coordinator data."""
    entity = hass.data["camera"].get_entity("camera.front_door_camera")

    # Camera should be available when in coordinator data
    assert entity.available is True


async def test_camera_unavailable_when_not_in_data(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
) -> None:
    """Test camera becomes unavailable when removed from coordinator data."""
    entity = hass.data["camera"].get_entity("camera.front_door_camera")

    # Remove camera from coordinator data
    entity.coordinator.data = {"cameras": {}}

    assert entity.available is False


async def test_camera_coordinator_update(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
) -> None:
    """Test camera updates from coordinator."""
    entity = hass.data["camera"].get_entity("camera.front_door_camera")

    # Update coordinator data with new camera info
    updated_camera = MagicMock()
    updated_camera.serial = "T1234567890"
    updated_camera.name = "Updated Camera Name"
    entity.coordinator.data = {"cameras": {"T1234567890": updated_camera}}

    entity._handle_coordinator_update()

    assert entity._camera == updated_camera


async def test_camera_supported_features(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test camera has stream support."""
    entity = hass.data["camera"].get_entity("camera.front_door_camera")
    assert entity.supported_features & CameraEntityFeature.STREAM


async def test_camera_rtsp_url_special_chars(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
) -> None:
    """Test RTSP URL properly encodes special characters in credentials."""
    # Set credentials with special characters
    mock_camera.rtsp_username = "user@test"
    mock_camera.rtsp_password = "pass/word#123"

    entity = hass.data["camera"].get_entity("camera.front_door_camera")
    stream_url = await entity.stream_source()

    # Special characters should be URL encoded
    assert "user%40test" in stream_url
    assert "pass%2Fword%23123" in stream_url


async def test_camera_stream_source_invalid_credentials(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
) -> None:
    """Test stream_source handles InvalidCredentialsError and triggers reauth."""
    # No RTSP credentials, so it will try cloud streaming
    mock_camera.rtsp_username = None
    mock_camera.rtsp_password = None
    mock_camera.async_start_stream = AsyncMock(
        side_effect=InvalidCredentialsError("Invalid credentials")
    )

    entity = hass.data["camera"].get_entity("camera.front_door_camera")

    with pytest.raises(HomeAssistantError):
        await entity.stream_source()


async def test_camera_stream_source_api_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test stream_source handles EufySecurityError."""
    # No RTSP credentials, so it will try cloud streaming
    mock_camera.rtsp_username = None
    mock_camera.rtsp_password = None
    mock_camera.async_start_stream = AsyncMock(
        side_effect=EufySecurityError("API error")
    )

    entity = hass.data["camera"].get_entity("camera.front_door_camera")

    with (
        caplog.at_level(logging.DEBUG, logger="homeassistant.components.eufy_security"),
        pytest.raises(HomeAssistantError),
    ):
        await entity.stream_source()

    # Check debug logging
    assert "Error calling stream_source" in caplog.text


async def test_camera_dynamic_addition(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
    mock_eufy_api: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test dynamic camera addition when coordinator detects new cameras."""
    # Initial setup should have one camera
    assert hass.states.get("camera.front_door_camera") is not None
    assert hass.states.get("camera.back_yard_camera") is None

    # Create a new camera
    new_camera = MagicMock()
    new_camera.serial = "T9999999999"
    new_camera.station_serial = "T0987654321"
    new_camera.name = "Back Yard Camera"
    new_camera.model = "eufyCam 3"
    new_camera.hardware_version = "3.0"
    new_camera.software_version = "3.0.1.0"
    new_camera.ip_address = "192.168.1.101"
    new_camera.last_camera_image_url = "https://example.com/image2.jpg"
    new_camera.rtsp_username = None
    new_camera.rtsp_password = None
    new_camera.async_start_stream = AsyncMock(return_value="rtsp://example.com/stream2")
    new_camera.async_stop_stream = AsyncMock()

    # Add new camera to the API
    mock_eufy_api.cameras[new_camera.serial] = new_camera

    # Simulate coordinator update by updating the data and triggering listeners
    coordinator = init_integration.runtime_data.coordinator
    coordinator.data = {
        "cameras": {
            mock_camera.serial: mock_camera,
            new_camera.serial: new_camera,
        },
        "stations": coordinator.data.get("stations", {}),
    }

    # Trigger the coordinator listeners
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    # New camera should now exist
    state = hass.states.get("camera.back_yard_camera")
    assert state is not None
    assert state.state == "idle"

    # Verify entity registry
    entry = entity_registry.async_get("camera.back_yard_camera")
    assert entry is not None
    assert entry.unique_id == "T9999999999-camera"
