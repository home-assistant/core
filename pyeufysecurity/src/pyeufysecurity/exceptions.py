"""Exceptions for Eufy Security API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .api import EufySecurityAPI


class EufySecurityError(Exception):
    """Base exception for Eufy Security errors."""


class InvalidCredentialsError(EufySecurityError):
    """Exception for invalid credentials."""


class RequestError(EufySecurityError):
    """Exception for request errors."""


class CannotConnectError(EufySecurityError):
    """Exception for connection failures."""


class CaptchaRequiredError(EufySecurityError):
    """Exception when CAPTCHA verification is required."""

    def __init__(
        self,
        message: str,
        captcha_id: str,
        captcha_image: str | None = None,
        api: EufySecurityAPI | None = None,
    ) -> None:
        """Initialize CAPTCHA error with details."""
        super().__init__(message)
        self.captcha_id = captcha_id
        self.captcha_image = captcha_image
        self.api = api  # Store the API instance to reuse for CAPTCHA retry


class InvalidCaptchaError(EufySecurityError):
    """Exception when CAPTCHA answer is invalid."""


# Map error codes to exceptions
ERROR_CODES: dict[int, type[Exception]] = {
    26006: InvalidCredentialsError,
    26050: InvalidCredentialsError,  # Wrong password
    100033: InvalidCaptchaError,  # Wrong CAPTCHA answer
}


def raise_on_error(data: dict[str, Any]) -> None:
    """Raise appropriate error based on response code."""
    code = data.get("code", 0)
    if code == 0:
        return
    error_class = ERROR_CODES.get(code, EufySecurityError)
    raise error_class(data.get("msg", f"Unknown error (code {code})"))
