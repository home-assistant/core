"""Errors for the Wyoming integration."""

from wyoming.error import Error

from homeassistant.exceptions import HomeAssistantError


class WyomingError(HomeAssistantError):
    """Base class for Wyoming errors."""


def error_event_details(error: Error) -> str:
    """Return the details of an error event from a Wyoming service."""
    if error.code is None:
        return error.text

    return f"{error.text} (code: {error.code})"


def error_event_message(error: Error) -> str:
    """Return a message for an error event from a Wyoming service."""
    return f"Error from Wyoming service: {error_event_details(error)}"
