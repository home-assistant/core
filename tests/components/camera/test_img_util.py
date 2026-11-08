"""Test img_util module."""

import logging
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


def test_turbojpeg_singleton() -> None:
    """Verify the instance always gives back the same."""
    _clear_turbojpeg_singleton()
    assert TurboJPEGSingleton.instance() == TurboJPEGSingleton.instance()


def test_scale_jpeg_camera_image() -> None:
    """Test we can scale a jpeg image."""
    _clear_turbojpeg_singleton()

    camera_image = Image("image/jpeg", EMPTY_16_12_JPEG)

    turbo_jpeg = mock_turbo_jpeg(first_width=16, first_height=12)
    with patch(
        "homeassistant.components.camera.img_util.TurboJPEG", return_value=False
    ):
        TurboJPEGSingleton()
        assert scale_jpeg_camera_image(camera_image, 16, 12) == camera_image.content

    turbo_jpeg = mock_turbo_jpeg(first_width=16, first_height=12)
    turbo_jpeg.decode_header.side_effect = OSError
    with patch(
        "homeassistant.components.camera.img_util.TurboJPEG", return_value=turbo_jpeg
    ):
        TurboJPEGSingleton()
        assert scale_jpeg_camera_image(camera_image, 16, 12) == camera_image.content

    turbo_jpeg = mock_turbo_jpeg(first_width=16, first_height=12)
    with patch(
        "homeassistant.components.camera.img_util.TurboJPEG", return_value=turbo_jpeg
    ):
        TurboJPEGSingleton()
        assert scale_jpeg_camera_image(camera_image, 16, 12) == EMPTY_16_12_JPEG

    turbo_jpeg = mock_turbo_jpeg(
        first_width=16, first_height=12, second_width=8, second_height=6
    )
    with patch(
        "homeassistant.components.camera.img_util.TurboJPEG", return_value=turbo_jpeg
    ):
        TurboJPEGSingleton()
        jpeg_bytes = scale_jpeg_camera_image(camera_image, 8, 6)

    assert jpeg_bytes == EMPTY_8_6_JPEG

    turbo_jpeg = mock_turbo_jpeg(
        first_width=640, first_height=480, second_width=640, second_height=480
    )
    with patch(
        "homeassistant.components.camera.img_util.TurboJPEG", return_value=turbo_jpeg
    ):
        TurboJPEGSingleton()
        jpeg_bytes = scale_jpeg_camera_image(camera_image, 320, 480)

    assert jpeg_bytes == EMPTY_16_12_JPEG


def _jpeg_with_exif_orientation(orientation: int, fill_bytes: int = 0) -> bytes:
    """Build a minimal JPEG header with an EXIF orientation tag."""
    tiff = (
        b"MM\x00\x2a\x00\x00\x00\x08"  # big endian TIFF header, IFD at offset 8
        b"\x00\x01"  # one IFD entry
        b"\x01\x12\x00\x03\x00\x00\x00\x01"  # orientation, SHORT, count 1
        + orientation.to_bytes(2, "big")
        + b"\x00\x00"
        + b"\x00\x00\x00\x00"  # no next IFD
    )
    payload = b"Exif\x00\x00" + tiff
    app1 = b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload
    return b"\xff\xd8" + b"\xff" * fill_bytes + app1 + b"\xff\xda\x00\x02image-data"


@pytest.mark.parametrize("fill_bytes", [0, 2])
def test_scale_jpeg_camera_image_preserves_exif(fill_bytes: int) -> None:
    """Test scaling keeps the EXIF segment so the orientation still applies."""
    _clear_turbojpeg_singleton()

    original = _jpeg_with_exif_orientation(6, fill_bytes)
    exif_segment = original[2 + fill_bytes : original.index(b"\xff\xda")]
    jfif_app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    scaled_without_exif = b"\xff\xd8" + jfif_app0 + b"\xff\xda\x00\x02scaled"

    turbo_jpeg = mock_turbo_jpeg(first_width=1600, first_height=1200)
    turbo_jpeg.scale_with_quality.return_value = scaled_without_exif
    with patch(
        "homeassistant.components.camera.img_util.TurboJPEG", return_value=turbo_jpeg
    ):
        TurboJPEGSingleton()
        jpeg_bytes = scale_jpeg_camera_image(Image("image/jpeg", original), 1230, 921)

    assert jpeg_bytes == (
        b"\xff\xd8" + jfif_app0 + exif_segment + b"\xff\xda\x00\x02scaled"
    )


def test_turbojpeg_load_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Handle libjpegturbo not being installed."""
    _clear_turbojpeg_singleton()
    with patch(
        "homeassistant.components.camera.img_util.TurboJPEG", side_effect=Exception
    ):
        TurboJPEGSingleton()
        assert TurboJPEGSingleton.instance() is False
        assert caplog.record_tuples == [
            (
                "homeassistant.components.camera.img_util",
                logging.ERROR,
                "Error loading libturbojpeg; Camera snapshot"
                " performance will be sub-optimal",
            )
        ]


def test_turbojpeg_load_success(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Handle libjpegturbo being installed."""
    _clear_turbojpeg_singleton()
    TurboJPEGSingleton()
    # Verify TurboJPEG was loaded successfully
    assert isinstance(TurboJPEGSingleton.instance(), TurboJPEG)
    assert caplog.record_tuples == []


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
