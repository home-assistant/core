"""Image processing for cameras."""

import logging
from typing import TYPE_CHECKING, Literal, cast

from turbojpeg import TurboJPEG

if TYPE_CHECKING:
    from . import Image

SUPPORTED_SCALING_FACTORS = [(7, 8), (3, 4), (5, 8), (1, 2), (3, 8), (1, 4), (1, 8)]

_LOGGER = logging.getLogger(__name__)

JPEG_QUALITY = 75

_JPEG_SOI = b"\xff\xd8"
_JPEG_APP0 = 0xE0
_JPEG_APP1 = 0xE1
_JPEG_SOS = 0xDA
_EXIF_HEADER = b"Exif\x00\x00"


def _find_exif_segment(jpeg: bytes) -> bytes | None:
    """Return the complete EXIF APP1 segment of a JPEG, or None if there is none."""
    if not jpeg.startswith(_JPEG_SOI):
        return None
    pos = 2
    while pos + 4 <= len(jpeg) and jpeg[pos] == 0xFF:
        # A marker may be preceded by any number of 0xFF fill bytes
        if jpeg[pos + 1] == 0xFF:
            pos += 1
            continue
        marker = jpeg[pos + 1]
        if marker == _JPEG_SOS:
            return None
        length = int.from_bytes(jpeg[pos + 2 : pos + 4], "big")
        if length < 2:
            return None
        end = pos + 2 + length
        if marker == _JPEG_APP1 and jpeg[pos + 4 : pos + 10] == _EXIF_HEADER:
            return jpeg[pos:end] if end <= len(jpeg) else None
        pos = end
    return None


def _insert_exif_segment(jpeg: bytes, exif_segment: bytes) -> bytes:
    """Insert an EXIF APP1 segment after SOI and an optional JFIF APP0 segment."""
    if not jpeg.startswith(_JPEG_SOI):
        return jpeg
    pos = 2
    if len(jpeg) >= pos + 4 and jpeg[pos] == 0xFF and jpeg[pos + 1] == _JPEG_APP0:
        pos += 2 + int.from_bytes(jpeg[pos + 2 : pos + 4], "big")
    return jpeg[:pos] + exif_segment + jpeg[pos:]


def find_supported_scaling_factor(
    current_width: int, current_height: int, target_width: int, target_height: int
) -> tuple[int, int] | None:
    """Find a supported scaling factor to scale the image.

    If there is no exact match, we use one size up to ensure
    the image remains crisp.
    """
    for idx, supported_sf in enumerate(SUPPORTED_SCALING_FACTORS):
        ratio = supported_sf[0] / supported_sf[1]
        width_after_scale = current_width * ratio
        height_after_scale = current_height * ratio
        if width_after_scale == target_width and height_after_scale == target_height:
            return supported_sf
        if width_after_scale < target_width or height_after_scale < target_height:
            return None if idx == 0 else SUPPORTED_SCALING_FACTORS[idx - 1]

    # Giant image, the most we can reduce by is 1/8
    return SUPPORTED_SCALING_FACTORS[-1]


def scale_jpeg_camera_image(cam_image: Image, width: int, height: int) -> bytes:
    """Scale a camera image.

    Scale as close as possible to one of the supported scaling factors.
    """
    turbo_jpeg = TurboJPEGSingleton.instance()
    if not turbo_jpeg:
        return cam_image.content

    try:
        (current_width, current_height, _, _) = turbo_jpeg.decode_header(
            cam_image.content
        )
    except OSError:
        return cam_image.content

    scaling_factor = find_supported_scaling_factor(
        current_width, current_height, width, height
    )
    if scaling_factor is None:
        return cam_image.content

    scaled = cast(
        bytes,
        turbo_jpeg.scale_with_quality(
            cam_image.content,
            scaling_factor=scaling_factor,
            quality=JPEG_QUALITY,
        ),
    )
    # TurboJPEG drops all APP segments when re-encoding. Keep the EXIF data so
    # the orientation tag still applies to the scaled image; otherwise a
    # rotated camera image is shown upright or sideways depending on whether
    # it was scaled.
    if exif_segment := _find_exif_segment(cam_image.content):
        return _insert_exif_segment(scaled, exif_segment)
    return scaled


class TurboJPEGSingleton:
    """Load TurboJPEG only once.

    Ensures we do not log load failures each snapshot
    since camera image fetches happen every few
    seconds.
    """

    __instance: TurboJPEG | Literal[False] | None = None

    @staticmethod
    def instance() -> TurboJPEG | Literal[False] | None:
        """Singleton for TurboJPEG."""
        if TurboJPEGSingleton.__instance is None:
            TurboJPEGSingleton()
        return TurboJPEGSingleton.__instance

    def __init__(self) -> None:
        """Try to create TurboJPEG only once."""
        try:
            TurboJPEGSingleton.__instance = TurboJPEG()
        except Exception:
            _LOGGER.exception(
                "Error loading libturbojpeg;"
                " Camera snapshot performance will be sub-optimal"
            )
            TurboJPEGSingleton.__instance = False


# TurboJPEG loads libraries that do blocking I/O.
# Initialize TurboJPEGSingleton in the executor to avoid
# blocking the event loop.
TurboJPEGSingleton.instance()
