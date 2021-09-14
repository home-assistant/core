"""Errors for the Transmission component."""
from homeassistant.exceptions import HomeAssistantError


class TransmissionrBaseError(HomeAssistantError):
    """Base exception for transmission client."""


class AuthenticationError(TransmissionrBaseError):
    """Wrong Username or Password."""


class CannotConnect(TransmissionrBaseError):
    """Unable to connect to client."""


class UnknownError(TransmissionrBaseError):
    """Unknown Error."""
