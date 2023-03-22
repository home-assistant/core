"""Test img_util module."""
from unittest.mock import patch

import pytest
from turbojpeg import TurboJPEG

from homeassistant.components.camera import Image
from homeassistant.components.camera.img_util import (
    TurboJPEGSingleton,
    find_supported_scaling_factor,
    scale_jpeg_camera_image,
)

from .common import EMPTY_8_6_JPEG, mock_turbo_jpeg

EMPTY_16_12_JPEG = b"empty_16_12"


def _clear_turbojpeg_singleton():
    TurboJPEGSingleton.__instance = None


def _reset_turbojpeg_singleton():
    TurboJPEGSingleton.__instance = TurboJPEG()


def test_turbojpeg_singleton() -> None:
    """Verify the instance always gives back the same."""
    _clear_turbojpeg_singleton()
    assert TurboJPEGSingleton.instance() == TurboJPEGSingleton.instance()


def test_scale_jpeg_camera_image() -> None:
    """Test we can scale a jpeg image."""
    _clear_turbojpeg_singleton()

    camera_image = Image("image/jpeg", EMPTY_16_12_JPEG)

    turbo_jpeg = mock_turbo_jpeg(first_width=16, first_height=12)
    with patch("turbojpeg.TurboJPEG", return_value=False):
        TurboJPEGSingleton()
        assert scale_jpeg_camera_image(camera_image, 16, 12) == camera_image.content

    turbo_jpeg = mock_turbo_jpeg(first_width=16, first_height=12)
    turbo_jpeg.decode_header.side_effect = OSError
    with patch("turbojpeg.TurboJPEG", return_value=turbo_jpeg):
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

    turbo_jpeg = mock_turbo_jpeg(
        first_width=640, first_height=480, second_width=640, second_height=480
    )
    with patch("turbojpeg.TurboJPEG", return_value=turbo_jpeg):
        TurboJPEGSingleton()
        jpeg_bytes = scale_jpeg_camera_image(camera_image, 320, 480)

    assert jpeg_bytes == EMPTY_16_12_JPEG


def test_turbojpeg_load_failure() -> None:
    """Handle libjpegturbo not being installed."""
    _clear_turbojpeg_singleton()
    with patch("turbojpeg.TurboJPEG", side_effect=Exception):
        TurboJPEGSingleton()
        assert TurboJPEGSingleton.instance() is False

    _clear_turbojpeg_singleton()
    TurboJPEGSingleton()
    assert TurboJPEGSingleton.instance() is not None


SCALE_TEST_EXPECTED = [
    (5782, 3946, 640, 480, (1, 8)),  # Maximum scale
    (1600, 1200, 640, 480, (1, 2)),  # Equal scale for width and height
    (1600, 1200, 1400, 1050, (7, 8)),  # Equal scale for width and height
    (1600, 1200, 1200, 900, (3, 4)),  # Equal scale for width and height
    (1600, 1200, 1000, 750, (5, 8)),  # Equal scale for width and height
    (1600, 1200, 600, 450, (3, 8)),  # Equal scale for width and height
    (1600, 1200, 400, 300, (1, 4)),  # Equal scale for width and height
    (1600, 1200, 401, 300, (3, 8)),  # Width is just a little to big, next size up
    (640, 480, 330, 200, (5, 8)),  # Preserve width clarity
    (640, 480, 300, 260, (5, 8)),  # Preserve height clarity
    (640, 480, 1200, 480, None),  # Request larger width - no scaling
    (640, 480, 640, 480, None),  # Request same - no scaling
    (640, 480, 640, 270, None),  # Request smaller height - no scaling
    (640, 480, 320, 480, None),  # Request smaller width - no scaling
]


@pytest.mark.parametrize(
    ("image_width", "image_height", "input_width", "input_height", "scaling_factor"),
    SCALE_TEST_EXPECTED,
)
def test_find_supported_scaling_factor(
    image_width, image_height, input_width, input_height, scaling_factor
) -> None:
    """Test we always get an image of at least the size we ask if its big enough."""

    assert (
        find_supported_scaling_factor(
            image_width, image_height, input_width, input_height
        )
        == scaling_factor
    )
