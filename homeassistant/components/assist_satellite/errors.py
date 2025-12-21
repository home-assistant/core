"""Errors for assist satellite."""

from homeassistant.exceptions import HomeAssistantError


class AssistSatelliteError(HomeAssistantError):
    """Base class for assist satellite errors."""


class SatelliteBusyError(AssistSatelliteError):
    """Satellite is busy and cannot handle the request."""
