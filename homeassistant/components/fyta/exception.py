"""Exception classes for FYTA integration."""

from homeassistant import exceptions


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there are invalid credentials."""


class InvalidPassword(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid password."""
