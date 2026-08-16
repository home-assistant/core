"""Tests for the Vivotek camera integration."""

from unittest.mock import AsyncMock, patch

from libpyvivotek.vivotek import VivotekCameraError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vivotek.camera import VivotekCam
from homeassistant.components.vivotek.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_camera_device_info(
    hass: HomeAssistant,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the camera is linked to a device with expected metadata."""
    mock_vivotek_camera.get_serial.return_value = "ABCD1234"
    mock_vivotek_camera.get_param.side_effect = lambda key: {
        "system_info_firmwareversion": "1.2.3",
        "system_info_modelname": "FD9165-HT",
    }[key]

    await setup_integration(hass, mock_config_entry)

    entity_entry = entity_registry.async_get("camera.vivotek_camera")
    assert entity_entry is not None
    assert entity_entry.device_id is not None

    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert (DOMAIN, "11:22:33:44:55:66") in device.identifiers
    assert device.manufacturer == "VIVOTEK"
    assert device.model == "FD9165-HT"
    assert device.serial_number == "ABCD1234"
    assert device.sw_version == "1.2.3"


async def test_camera_device_info_with_metadata_errors(
    hass: HomeAssistant,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test metadata fields are omitted when camera metadata calls fail."""
    mock_vivotek_camera.get_serial.side_effect = VivotekCameraError
    mock_vivotek_camera.get_param.side_effect = VivotekCameraError

    await setup_integration(hass, mock_config_entry)

    entity_entry = entity_registry.async_get("camera.vivotek_camera")
    assert entity_entry is not None
    assert entity_entry.device_id is not None

    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.model is None
    assert device.serial_number is None
    assert device.sw_version is None


def test_camera_available_when_update_succeeds(
    mock_vivotek_camera: AsyncMock,
) -> None:
    """Test camera is available when update probe succeeds."""
    camera = VivotekCam(
        mock_vivotek_camera,
        "rtsp://example/live.sdp",
        "11:22:33:44:55:66",
        None,
        None,
        None,
        2,
        "Vivotek Camera",
    )

    camera.update()

    assert camera.available


def test_camera_unavailable_when_update_fails(
    mock_vivotek_camera: AsyncMock,
) -> None:
    """Test camera is unavailable when update probe raises error."""
    camera = VivotekCam(
        mock_vivotek_camera,
        "rtsp://example/live.sdp",
        "11:22:33:44:55:66",
        None,
        None,
        None,
        2,
        "Vivotek Camera",
    )
    mock_vivotek_camera.get_serial.side_effect = VivotekCameraError

    camera.update()

    assert not camera.available


async def test_camera_stream_source(
    mock_vivotek_camera: AsyncMock,
) -> None:
    """Test stream source is returned from camera entity."""
    camera = VivotekCam(
        mock_vivotek_camera,
        "rtsp://example/live.sdp",
        "11:22:33:44:55:66",
        None,
        None,
        None,
        2,
        "Vivotek Camera",
    )

    stream_source = await camera.stream_source()

    assert stream_source == "rtsp://example/live.sdp"


def test_camera_motion_detection_methods(
    mock_vivotek_camera: AsyncMock,
) -> None:
    """Test motion detection commands update entity state."""
    camera = VivotekCam(
        mock_vivotek_camera,
        "rtsp://example/live.sdp",
        "11:22:33:44:55:66",
        None,
        None,
        None,
        2,
        "Vivotek Camera",
    )
    mock_vivotek_camera.set_param.side_effect = ["1", "0"]

    camera.enable_motion_detection()
    assert camera.motion_detection_enabled

    camera.disable_motion_detection()
    assert not camera.motion_detection_enabled


def test_camera_image_returns_snapshot(
    mock_vivotek_camera: AsyncMock,
) -> None:
    """Test camera image comes directly from camera snapshot call."""
    camera = VivotekCam(
        mock_vivotek_camera,
        "rtsp://example/live.sdp",
        "11:22:33:44:55:66",
        None,
        None,
        None,
        2,
        "Vivotek Camera",
    )
    mock_vivotek_camera.snapshot.return_value = b"snapshot-bytes"

    image = camera.camera_image()

    assert image == b"snapshot-bytes"
