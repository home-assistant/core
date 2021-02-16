"""Errors for the binance integration."""
from homeassistant.exceptions import HomeAssistantError


class BinanceException(HomeAssistantError):
    """Base class for Binance exceptions."""


class InvalidAuth(BinanceException):
    """Error to indicate there is invalid auth."""


class InvalidResponse(BinanceException):
    """Error to indicate the API response is invalid."""
