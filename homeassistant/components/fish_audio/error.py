"""Exceptions for the Fish Audio integration."""

import logging

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__package__)


class FishAudioError(HomeAssistantError):
    """Base class for Fish Audio errors."""


class CannotConnectError(FishAudioError):
    """Error to indicate we cannot connect."""

    def __init__(self, exc: Exception) -> None:
        """Initialize the connection error."""
        super().__init__("Cannot connect")


class InvalidAuthError(FishAudioError):
    """Error to indicate invalid authentication."""

    def __init__(self, exc: Exception) -> None:
        """Initialize the invalid auth error."""
        super().__init__("Invalid authentication")


class CannotGetModelsError(FishAudioError):
    """Error to indicate we cannot get models."""

    def __init__(self, exc: Exception) -> None:
        """Initialize the model fetch error."""
        super().__init__("Cannot get models")


class UnexpectedError(FishAudioError):
    """Error to indicate an unexpected error."""

    def __init__(self, exc: Exception) -> None:
        """Initialize and log the unexpected error."""
        super().__init__("Unexpected error")
        _LOGGER.exception("Unexpected exception: %s", exc)


class AlreadyConfiguredError(FishAudioError):
    """Error to indicate already configured."""

    def __init__(self, exc: Exception) -> None:
        """Initialize the already configured error."""
        super().__init__("Already configured")
