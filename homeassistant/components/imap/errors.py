"""Exceptions raised by IMAP integration."""

from homeassistant.exceptions import HomeAssistantError


class InvalidAuth(HomeAssistantError):
    """Raise exception for invalid credentials."""


class InvalidFolder(HomeAssistantError):
    """Raise exception for invalid folder."""
