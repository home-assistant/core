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


class InvalidMessage(HassClientError):
    """The websocket server returned an invalid message."""


class NotConnected(HassClientError):
    """The client is not connected."""
