"""Errors for the bittrex integration."""
from homeassistant.exceptions import HomeAssistantError


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidMarket(HomeAssistantError):
    """Error to indicate the market is invalid."""
