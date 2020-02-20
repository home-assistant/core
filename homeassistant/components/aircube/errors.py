"""Errors for the airCube component."""
from homeassistant.exceptions import HomeAssistantError


class AirCubeException(HomeAssistantError):
    """Base class for airCube exceptions."""


class LoginError(AirCubeException):
    """Authentication error: Check username and password."""


class SSLError(AirCubeException):
    """SSL error. Set VERIFY_SSL to False."""


class ConnectionTimeout(AirCubeException):
    """Connection timed out. Check IP address and connection to router."""


class CannotConnect(AirCubeException):
    """Unable to connect to router."""
