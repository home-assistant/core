"""Exceptions raised by VegeHub integration."""

from homeassistant.exceptions import HomeAssistantError


class MissingInformation(HomeAssistantError):
    """Raise exception for missing information that was expected."""


class CommunicationFailed(HomeAssistantError):
    """Raise exception for failure to communicate with target."""
