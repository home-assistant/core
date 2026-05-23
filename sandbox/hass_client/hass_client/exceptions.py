"""Client exceptions."""

from __future__ import annotations


class HassClientError(Exception):
    """Base client exception."""


class AuthenticationFailed(HassClientError):
    """Authentication failed."""


class CannotConnect(HassClientError):
    """The websocket connection could not be established."""


class ConnectionFailed(HassClientError):
    """The websocket listener failed."""


class ConnectionFailedDueToLargeMessage(ConnectionFailed):
    """The websocket listener failed due to a large message."""


class FailedCommand(HassClientError):
    """A websocket command returned an error."""

    def __init__(
        self,
        message: str,
        *,
        command: str | None = None,
        code: str | None = None,
        translation_domain: str | None = None,
        translation_key: str | None = None,
        translation_placeholders: dict[str, str] | None = None,
    ) -> None:
        """Initialize the failed command error."""
        super().__init__(message)
        self.command = command
        self.code = code
        self.translation_domain = translation_domain
        self.translation_key = translation_key
        self.translation_placeholders = translation_placeholders


class InvalidMessage(HassClientError):
    """The websocket server returned an invalid message."""


class NotConnected(HassClientError):
    """The client is not connected."""
