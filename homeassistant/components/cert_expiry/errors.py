"""Errors for the cert_expiry integration."""

from typing import ClassVar, override


class CertExpiryException(Exception):
    """Base class for cert_expiry exceptions."""

    translation_key: ClassVar[str]

    def __init__(self, host: str, port: int) -> None:
        """Initialize the error for the host and port."""
        super().__init__(host, port)
        self.host = host
        self.port = port

    @property
    def translation_placeholders(self) -> dict[str, str]:
        """Return the placeholders for the translated message."""
        return {"host": self.host, "port": str(self.port)}


class TemporaryFailure(CertExpiryException):
    """Temporary failure has occurred."""


class ValidationFailure(CertExpiryException):
    """Certificate validation failure has occurred."""


class NoCertificate(ValidationFailure):
    """The server did not present a certificate."""

    translation_key = "no_certificate"


class InvalidCertificate(ValidationFailure):
    """The server presented a certificate that could not be parsed."""

    translation_key = "invalid_certificate"


class HandshakeFailed(ValidationFailure):
    """The TLS handshake failed."""

    translation_key = "handshake_failed"

    def __init__(self, host: str, port: int, error: str) -> None:
        """Initialize the error with the SSL error description."""
        super().__init__(host, port)
        self.error = error

    @property
    @override
    def translation_placeholders(self) -> dict[str, str]:
        """Return the placeholders, including the SSL error description."""
        return {**super().translation_placeholders, "error": self.error}


class ResolveFailed(TemporaryFailure):
    """Name resolution failed."""

    translation_key = "resolve_failed"


class ConnectionTimeout(TemporaryFailure):
    """Network connection timed out."""

    translation_key = "connection_timeout"


class ConnectionRefused(TemporaryFailure):
    """Network connection refused."""

    translation_key = "connection_refused"


class ConnectionReset(TemporaryFailure):
    """Network connection reset."""

    translation_key = "connection_reset"


class ConnectionFailed(TemporaryFailure):
    """Network connection failed."""

    translation_key = "connection_failed"
