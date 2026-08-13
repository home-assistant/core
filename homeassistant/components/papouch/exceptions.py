"""Exceptions for the Papouch integration."""

from typing import Any

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


class PapouchConnectionError(HomeAssistantError):
    """Exception raised when connection to the Papouch device fails."""

    def __init__(self, translation_placeholders: dict[str, Any] | None = None) -> None:
        """Initialize connection error with translation attributes."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders=translation_placeholders,
        )


class PapouchAuthError(HomeAssistantError):
    """Exception raised when authentication fails."""

    def __init__(self, translation_placeholders: dict[str, Any] | None = None) -> None:
        """Initialize authentication error with translation attributes."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
            translation_placeholders=translation_placeholders,
        )


class PapouchCommandError(HomeAssistantError):
    """Exception raised when a command fails to execute."""

    def __init__(self, translation_placeholders: dict[str, Any] | None = None) -> None:
        """Initialize command error with translation attributes."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="command_failed",
            translation_placeholders=translation_placeholders,
        )
