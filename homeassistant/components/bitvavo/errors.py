"""Errors for the Bitvavo integration."""
from homeassistant.exceptions import HomeAssistantError


class BitvavoException(HomeAssistantError):
    """Base class for Bitvavo exceptions."""


class InvalidAuth(BitvavoException):
    """Error to indicate there is invalid auth."""


class InvalidResponse(BitvavoException):
    """Error to indicate the API response is invalid."""
