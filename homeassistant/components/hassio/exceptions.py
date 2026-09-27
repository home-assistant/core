"""Exceptions for the Hassio integration."""

from homeassistant.exceptions import HomeAssistantError


class HassioNotReadyError(HomeAssistantError):
    """Raised when Hassio data is not yet available."""
