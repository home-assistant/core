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


SOI = b"\xff\xd8"
SOS = b"\xff\xda\x00\x02"
JFIF_APP0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
EXIF_PAYLOAD = (
    b"Exif\x00\x00"
    b"MM\x00\x2a\x00\x00\x00\x08"  # big endian TIFF header, IFD at offset 8
    b"\x00\x01"  # one IFD entry
    b"\x01\x12\x00\x03\x00\x00\x00\x01\x00\x06\x00\x00"  # orientation 6
    b"\x00\x00\x00\x00"  # no next IFD
)
EXIF_APP1 = b"\xff\xe1" + (len(EXIF_PAYLOAD) + 2).to_bytes(2, "big") + EXIF_PAYLOAD
SCALED = SOI + JFIF_APP0 + SOS + b"scaled"


@pytest.mark.parametrize(
    ("original", "scaled", "expected"),
    [
        # EXIF is copied behind the JFIF APP0 segment of the scaled image
        (
            SOI + EXIF_APP1 + SOS + b"image",
            SCALED,
            SOI + JFIF_APP0 + EXIF_APP1 + SOS + b"scaled",
        ),
        # Fill bytes before a marker are skipped
        (
            SOI + b"\xff\xff" + EXIF_APP1 + SOS + b"image",
            SCALED,
            SOI + JFIF_APP0 + EXIF_APP1 + SOS + b"scaled",
        ),
        # Markers without a length field (TEM) are skipped
        (
            SOI + b"\xff\x01" + EXIF_APP1 + SOS + b"image",
            SCALED,
            SOI + JFIF_APP0 + EXIF_APP1 + SOS + b"scaled",
        ),
        # EXIF after another APP segment is found
        (
            SOI + JFIF_APP0 + EXIF_APP1 + SOS + b"image",
            SCALED,
            SOI + JFIF_APP0 + EXIF_APP1 + SOS + b"scaled",
        ),
        # Scaled image without APP0 gets EXIF right after SOI
        (
            SOI + EXIF_APP1 + SOS + b"image",
            SOI + SOS + b"scaled",
            SOI + EXIF_APP1 + SOS + b"scaled",
        ),
        # No EXIF in the source image
        (SOI + JFIF_APP0 + SOS + b"image", SCALED, SCALED),
        # Header ends without a start of scan
        (SOI, SCALED, SCALED),
        # Invalid segment length
        (SOI + b"\xff\xe1\x00\x01" + SOS + b"image", SCALED, SCALED),
        # Truncated EXIF segment
        (SOI + EXIF_APP1[:-4], SCALED, SCALED),
        # Scaled data is not a JPEG
        (SOI + EXIF_APP1 + SOS + b"image", b"not-a-jpeg", b"not-a-jpeg"),
    ],
)
def test_scale_jpeg_camera_image_preserves_exif(
    original: bytes, scaled: bytes, expected: bytes
) -> None:
    """Test scaling keeps the EXIF segment so the orientation still applies."""
    _clear_turbojpeg_singleton()

    turbo_jpeg = mock_turbo_jpeg(first_width=1600, first_height=1200)
    turbo_jpeg.scale_with_quality.return_value = scaled
    with patch(
        "homeassistant.components.camera.img_util.TurboJPEG", return_value=turbo_jpeg
    ):
        TurboJPEGSingleton()
        jpeg_bytes = scale_jpeg_camera_image(Image("image/jpeg", original), 600, 400)

    assert jpeg_bytes == expected


def _exif_app1(tiff: bytes) -> bytes:
    """Build an EXIF APP1 segment around a TIFF structure."""
    payload = b"Exif\x00\x00" + tiff
    return b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload


ORIENTATION_6_LITTLE_ENDIAN = (
    b"II\x2a\x00\x08\x00\x00\x00"  # little endian TIFF header, IFD at offset 8
    b"\x01\x00"  # one IFD entry
    b"\x12\x01\x03\x00\x01\x00\x00\x00\x06\x00\x00\x00"  # orientation 6
    b"\x00\x00\x00\x00"  # no next IFD
)


@pytest.mark.parametrize(
    ("exif_app1", "scaling_factor"),
    [
        # Orientation 6: the 1600x1200 image is displayed as 1200x1600
        (EXIF_APP1, (1, 2)),
        (_exif_app1(ORIENTATION_6_LITTLE_ENDIAN), (1, 2)),
        # Orientation 1 and missing or unreadable orientation keep the stored size
        (_exif_app1(EXIF_PAYLOAD[6:].replace(b"\x00\x06", b"\x00\x01", 1)), (3, 8)),
        (b"", (3, 8)),
        (_exif_app1(b"XX" + EXIF_PAYLOAD[8:]), (3, 8)),
        (_exif_app1(EXIF_PAYLOAD[6:14]), (3, 8)),
        (_exif_app1(b"MM\x00\x2a\x00\x00\x00\x08\x00\x00"), (3, 8)),
    ],
)
def test_scale_jpeg_camera_image_uses_exif_orientation(
    exif_app1: bytes, scaling_factor: tuple[int, int]
) -> None:
    """Test the scaling factor is chosen for the displayed orientation."""
    _clear_turbojpeg_singleton()

    turbo_jpeg = mock_turbo_jpeg(first_width=1600, first_height=1200)
    turbo_jpeg.scale_with_quality.return_value = SCALED
    with patch(
        "homeassistant.components.camera.img_util.TurboJPEG", return_value=turbo_jpeg
    ):
        TurboJPEGSingleton()
        scale_jpeg_camera_image(
            Image("image/jpeg", SOI + exif_app1 + SOS + b"image"), 600, 400
        )

    assert (
        turbo_jpeg.scale_with_quality.call_args.kwargs["scaling_factor"]
        == scaling_factor
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
