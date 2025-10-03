"""Test the Vivotek camera platform."""

from unittest.mock import MagicMock

from homeassistant.components.vivotek.camera import VivotekCam
from homeassistant.core import HomeAssistant

from .conftest import TEST_CAM_NAME, TEST_CONFIG


async def test_camera(
    hass: HomeAssistant,
    vivotek_camera: MagicMock,
) -> None:
    """Test camera entity with fluent."""

    config = TEST_CONFIG
    stream_source = "rtsp://usr:pwd@127.1.2.3:554/live.sdp"
    cam = VivotekCam(config, vivotek_camera, stream_source)

    assert cam.name == TEST_CAM_NAME

    assert await cam.stream_source() == stream_source

    assert cam.camera_image() == b"image_bytes"
