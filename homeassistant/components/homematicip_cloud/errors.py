"""Errors for the HomematicIP component."""
from homeassistant.exceptions import HomeAssistantError


class HmipcException(HomeAssistantError):
    """Base class for HomematicIP exceptions."""


class HmipcConnectionError(HmipcException):
    """Unable to connect to the HomematicIP cloud server."""


class HmipcConnectionWait(HmipcException):
    """Wait for registration to the HomematicIP cloud server."""


class HmipcRegistrationFailed(HmipcException):
    """Registration on HomematicIP cloud failed."""


class HmipcPressButton(HmipcException):
    """User needs to press the blue button."""
