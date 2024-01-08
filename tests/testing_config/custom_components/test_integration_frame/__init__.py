"""An integration which calls helpers.frame.get_integration_frame."""

from homeassistant.helpers import frame


def call_get_integration_frame() -> frame.IntegrationFrame:
    """Call get_integration_frame."""
    return frame.get_integration_frame()
