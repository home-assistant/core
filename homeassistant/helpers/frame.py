"""Provide frame helper for finding the current frame context."""
from traceback import FrameSummary, extract_stack
from typing import Tuple

from homeassistant.exceptions import HomeAssistantError


def get_integration_frame() -> Tuple[FrameSummary, str, str]:
    """Return the frame, integration and integration path of the current stack frame."""
    found_frame = None

    for frame in reversed(extract_stack()):
        for path in ("custom_components/", "homeassistant/components/"):
            try:
                index = frame.filename.index(path)
                found_frame = frame
                break
            except ValueError:
                continue

        if found_frame is not None:
            break

    if found_frame is None:
        raise MissingIntegrationFrame

    start = index + len(path)
    end = found_frame.filename.index("/", start)

    integration = found_frame.filename[start:end]

    return found_frame, integration, path


class MissingIntegrationFrame(HomeAssistantError):
    """Raised when no integration is found in the frame."""
