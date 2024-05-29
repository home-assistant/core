"""Image processing for cameras."""

from __future__ import annotations

from contextlib import suppress
import logging
from typing import TYPE_CHECKING, Literal, cast

with suppress(Exception):
    # TurboJPEG imports numpy which may or may not work so
    # we have to guard the import here. We still want
    # to import it at top level so it gets loaded
    # in the import executor and not in the event loop.
    from turbojpeg import TurboJPEG


if TYPE_CHECKING:
    from . import Image

SUPPORTED_SCALING_FACTORS = [(7, 8), (3, 4), (5, 8), (1, 2), (3, 8), (1, 4), (1, 8)]

_LOGGER = logging.getLogger(__name__)

JPEG_QUALITY = 75


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

    return cast(
        bytes,
        turbo_jpeg.scale_with_quality(
            cam_image.content,
            scaling_factor=scaling_factor,
            quality=JPEG_QUALITY,
        ),
    )


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
                "Error loading libturbojpeg; Camera snapshot performance will be sub-optimal"
            )
            TurboJPEGSingleton.__instance = False


# TurboJPEG loads libraries that do blocking I/O.
# Initialize TurboJPEGSingleton in the executor to avoid
# blocking the event loop.
TurboJPEGSingleton.instance()
