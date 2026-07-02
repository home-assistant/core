"""Tests for the Amcrest camera platform."""

from unittest.mock import MagicMock

from amcrest import AmcrestError
import pytest

from homeassistant.components.amcrest import AmcrestDevice
from homeassistant.components.amcrest.camera import AmcrestCam
from homeassistant.components.ffmpeg import FFmpegManager

from .conftest import CAMERA_NAME, _MockAmcrestAPI


def _make_camera(device: AmcrestDevice) -> AmcrestCam:
    ffmpeg = MagicMock(spec=FFmpegManager)
    ffmpeg.binary = "/usr/bin/ffmpeg"
    return AmcrestCam(CAMERA_NAME, device, ffmpeg)


async def test_camera_update_populates_attributes(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """async_update fetches brand, model, RTSP URL, and streaming state."""
    camera = _make_camera(device)
    await camera.async_update()

    assert camera.brand == "Amcrest"
    assert camera.model == "IP2M-841"
    assert camera.is_on is True  # is_streaming = True from video_enabled
    assert camera.is_recording is False
    assert camera.motion_detection_enabled is False
    assert camera.extra_state_attributes["audio"] == "off"
    assert camera.extra_state_attributes["motion_recording"] == "off"
    assert camera.extra_state_attributes["color_bw"] == "color"


async def test_camera_update_skips_when_unavailable(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """async_update makes no API calls when the camera is unavailable."""
    mock_api.available = False
    camera = _make_camera(device)
    await camera.async_update()
    # Brand and model stay None — confirms no API contact was made
    assert camera.brand is None
    assert camera.model is None


async def test_camera_update_handles_error(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """AmcrestError during update is caught and does not propagate."""
    mock_api.set_error("vendor_information", AmcrestError("timeout"))
    camera = _make_camera(device)
    await camera.async_update()  # must not raise


async def test_camera_brand_only_fetched_once(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """Brand and model are only fetched on the first successful update."""
    camera = _make_camera(device)
    await camera.async_update()
    first_brand = camera.brand

    mock_api.vendor = "OtherBrand"
    await camera.async_update()
    assert camera.brand == first_brand  # not re-fetched


@pytest.mark.parametrize(
    "vendor",
    [
        pytest.param("", id="empty_string"),
        pytest.param(None, id="none"),
    ],
)
async def test_camera_unknown_brand_fallback(
    mock_api: _MockAmcrestAPI,
    device: AmcrestDevice,
    vendor: str | None,
) -> None:
    """Brand falls back to 'unknown' when the camera returns falsy vendor info."""
    mock_api.vendor = vendor
    camera = _make_camera(device)
    await camera.async_update()
    assert camera.brand == "unknown"
