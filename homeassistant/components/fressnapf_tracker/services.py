"""Services and service helpers for fressnapf_tracker."""

from fressnapftracker import FressnapfTrackerError, FressnapfTrackerInvalidTokenError

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from .const import DOMAIN


def handle_fressnapf_tracker_exception(exception: FressnapfTrackerError):
    """Handle the different FressnapfTracker errors."""
    if isinstance(exception, FressnapfTrackerInvalidTokenError):
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from exception
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="api_error",
        translation_placeholders={"error_message": str(exception)},
    ) from exception
