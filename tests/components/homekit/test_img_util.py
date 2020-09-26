"""Test HomeKit img_util module."""
from homeassistant.components.camera import Image
from homeassistant.components.homekit.img_util import (
    TurboJPEGSingleton,
    scale_jpeg_camera_image,
)

from .common import EMPTY_8_6_JPEG, mock_turbo_jpeg

from tests.async_mock import patch

EMPTY_16_12_JPEG = b"empty_16_12"


def test_turbojpeg_singleton():
    """Verify the instance always gives back the same."""
    assert TurboJPEGSingleton.instance() == TurboJPEGSingleton.instance()


def test_scale_jpeg_camera_image():
    """Test we can scale a jpeg image."""

    camera_image = Image("image/jpeg", EMPTY_16_12_JPEG)

    turbo_jpeg = mock_turbo_jpeg(first_width=16, first_height=12)
    with patch("turbojpeg.TurboJPEG", return_value=False):
        TurboJPEGSingleton()
        assert scale_jpeg_camera_image(camera_image, 16, 12) == camera_image.content

    turbo_jpeg = mock_turbo_jpeg(first_width=16, first_height=12)
    with patch("turbojpeg.TurboJPEG", return_value=turbo_jpeg):
        TurboJPEGSingleton()
        assert scale_jpeg_camera_image(camera_image, 16, 12) == EMPTY_16_12_JPEG

    turbo_jpeg = mock_turbo_jpeg(
        first_width=16, first_height=12, second_width=8, second_height=6
    )
    with patch("turbojpeg.TurboJPEG", return_value=turbo_jpeg):
        TurboJPEGSingleton()
        jpeg_bytes = scale_jpeg_camera_image(camera_image, 8, 6)

    assert jpeg_bytes == EMPTY_8_6_JPEG


def test_turbojpeg_load_failure():
    """Handle libjpegturbo not being installed."""

    with patch("turbojpeg.TurboJPEG", side_effect=Exception):
        TurboJPEGSingleton()
        assert TurboJPEGSingleton.instance() is False

    with patch("turbojpeg.TurboJPEG"):
        TurboJPEGSingleton()
        assert TurboJPEGSingleton.instance()
