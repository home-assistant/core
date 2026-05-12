"""Errors for the FlowSpeech integration."""


class FlowSpeechIntegrationError(Exception):
    """Base error for FlowSpeech integration setup."""


class CannotConnectError(FlowSpeechIntegrationError):
    """Raised when FlowSpeech cannot be reached."""


class InvalidAuthError(FlowSpeechIntegrationError):
    """Raised when FlowSpeech rejects credentials."""


class UnexpectedError(FlowSpeechIntegrationError):
    """Raised when an unexpected setup error occurs."""

