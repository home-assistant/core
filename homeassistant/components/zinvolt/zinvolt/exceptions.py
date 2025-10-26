"""Asynchronous Python client for Zinvolt."""


class ZinvoltError(Exception):
    """Generic exception."""


class ZinvoltAuthenticationError(ZinvoltError):
    """Authentication error."""
