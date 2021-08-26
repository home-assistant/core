"""Errors for the HomeWizard Energy component."""
from homeassistant.exceptions import HomeAssistantError


class HwEnergyException(HomeAssistantError):
    """Base class for HomeWizard Energy exceptions."""


class CannotConnect(HwEnergyException):
    """Unable to connect to the energy Device."""


class AuthenticationRequired(HwEnergyException):
    """Unknown error occurred."""
