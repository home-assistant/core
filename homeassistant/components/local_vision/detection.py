"""The detector of an entry and checks of frames against it."""

from collections.abc import Mapping

from tarsius import Roi, StateDetector

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


async def async_create_detector(
    hass: HomeAssistant, region: Mapping[str, float]
) -> StateDetector:
    """Create an untaught detector for a stored region.

    tarsius picks the model for the task. The first detector loads it,
    a blocking read that raises BackendError when it fails.
    """
    return await hass.async_add_executor_job(
        StateDetector, region_to_roi(region), STATES
    )


def _check_frame(frame: bytes, region: Mapping[str, float]) -> None:
    StateDetector(region_to_roi(region), STATES).prepare(frame)


async def async_check_frame(
    hass: HomeAssistant, frame: bytes, region: Mapping[str, float]
) -> None:
    """Check that a frame could be taught with this region.

    Raises tarsius ImageError, BlankFrameError, BlankRegionError, RoiError
    or BackendError.
    """
    await hass.async_add_executor_job(_check_frame, frame, region)
