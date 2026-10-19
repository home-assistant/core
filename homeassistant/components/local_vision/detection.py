"""The detector of an entry and checks of frames against it."""

from collections.abc import Mapping

from tarsius import EdgeBackend, Roi, StateDetector

from homeassistant.core import HomeAssistant

from .const import STATES

# Flow error key for each axis a tarsius RoiError names.
ROI_ERRORS = {
    "horizontal": "invalid_horizontal_range",
    "vertical": "invalid_vertical_range",
}


def region_to_roi(region: Mapping[str, float]) -> Roi:
    """Convert a stored region in percent; raise RoiError when it is empty."""
    return Roi.from_percent(**region)


def create_detector(region: Mapping[str, float]) -> StateDetector:
    """Create an untaught detector for a stored region."""
    return StateDetector(EdgeBackend(), region_to_roi(region), STATES)


async def async_check_frame(
    hass: HomeAssistant, frame: bytes, region: Mapping[str, float]
) -> None:
    """Check that a frame could be taught with this region.

    Raises tarsius ImageError, BlankFrameError or BlankRegionError.
    """
    await hass.async_add_executor_job(create_detector(region).prepare, frame)
