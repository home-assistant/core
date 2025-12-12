"""Python library for Eufy Security cameras and devices.

Based on eufy-security-client by bropat.
"""

from .api import EufySecurityAPI, async_login
from .exceptions import (
    CannotConnectError,
    CaptchaRequiredError,
    EufySecurityError,
    InvalidCaptchaError,
    InvalidCredentialsError,
    RequestError,
)
from .models import Camera, Station

__all__ = [
    "EufySecurityAPI",
    "async_login",
    "Camera",
    "Station",
    "EufySecurityError",
    "InvalidCredentialsError",
    "RequestError",
    "CannotConnectError",
    "CaptchaRequiredError",
    "InvalidCaptchaError",
]

__version__ = "1.0.0"
