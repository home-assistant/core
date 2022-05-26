"""Errors for the Transmission component."""
from homeassistant.exceptions import HomeAssistantError


class TrasnmissionrBaseError(HomeAssistantError):
    """Base exception for transmission client."""


class AuthenticationError(TrasnmissionrBaseError):
    """Wrong Username or Password."""


class CannotConnect(TrasnmissionrBaseError):
    """Unable to connect to client."""


class UnknownError(TrasnmissionrBaseError):
    """Unknown Error."""
