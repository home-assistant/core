"""Errors for the bittrex integration."""
from homeassistant.exceptions import HomeAssistantError


class BittrexException(HomeAssistantError):
    """Base class for Bittrex exceptions."""


class CannotConnect(BittrexException):
    """Error to indicate we cannot connect."""


class InvalidAuth(BittrexException):
    """Error to indicate there is invalid auth."""


class InvalidResponse(BittrexException):
    """Error to indicate the API response is invalid."""
