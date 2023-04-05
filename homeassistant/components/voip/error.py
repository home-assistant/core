"""Errors for VoIP integration."""


class VoipError(Exception):
    """Voice over IP error."""


class RtpError(VoipError):
    """Realtime Transport Protocol error."""
