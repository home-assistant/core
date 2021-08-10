"""Image processing for HomeKit component."""

import logging

SUPPORTED_SCALING_FACTORS = [(7, 8), (3, 4), (5, 8), (1, 2), (3, 8), (1, 4), (1, 8)]

_LOGGER = logging.getLogger(__name__)


def scale_jpeg_camera_image(cam_image, width, height):
    """Scale a camera image as close as possible to one of the supported scaling factors."""
    turbo_jpeg = TurboJPEGSingleton.instance()
    if not turbo_jpeg:
        return cam_image.content

    (current_width, current_height, _, _) = turbo_jpeg.decode_header(cam_image.content)

    if current_width <= width or current_height <= height:
        return cam_image.content

    ratio = width / current_width

    scaling_factor = SUPPORTED_SCALING_FACTORS[-1]
    for supported_sf in SUPPORTED_SCALING_FACTORS:
        if ratio >= (supported_sf[0] / supported_sf[1]):
            scaling_factor = supported_sf
            break

    return turbo_jpeg.scale_with_quality(
        cam_image.content,
        scaling_factor=scaling_factor,
        quality=75,
    )


class TurboJPEGSingleton:
    """
    Load TurboJPEG only once.

    Ensures we do not log load failures each snapshot
    since camera image fetches happen every few
    seconds.
    """

    __instance = None

    @staticmethod
    def instance():
        """Singleton for TurboJPEG."""
        if TurboJPEGSingleton.__instance is None:
            TurboJPEGSingleton()
        return TurboJPEGSingleton.__instance

    def __init__(self):
        """Try to create TurboJPEG only once."""
        # pylint: disable=unused-private-member
        # https://github.com/PyCQA/pylint/issues/4681
        try:
            # TurboJPEG checks for libturbojpeg
            # when its created, but it imports
            # numpy which may or may not work so
            # we have to guard the import here.
            from turbojpeg import TurboJPEG  # pylint: disable=import-outside-toplevel

            TurboJPEGSingleton.__instance = TurboJPEG()
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Error loading libturbojpeg; Cameras may impact HomeKit performance"
            )
            TurboJPEGSingleton.__instance = False
