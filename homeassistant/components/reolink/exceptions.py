"""Exceptions for the Reolink Camera integration."""

from homeassistant.exceptions import HomeAssistantError


class ReolinkException(HomeAssistantError):
    """BaseException for the Reolink integration."""


class ReolinkSetupException(ReolinkException):
    """Raised when setting up the Reolink host failed."""


class ReolinkWebhookException(ReolinkException):
    """Raised when registering the reolink webhook failed."""


class UserNotAdmin(ReolinkException):
    """Raised when user is not admin."""


class PasswordIncompatible(ReolinkException):
    """Raised when the password contains special chars that are incompatible."""
