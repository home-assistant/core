"""An integration which calls helpers.frame.get_integration_frame."""

import logging

from homeassistant.helpers import frame


def call_get_integration_logger(fallback_name: str) -> logging.Logger:
    """Call get_integration_logger."""
    return frame.get_integration_logger(fallback_name)


def call_get_integration_frame() -> frame.IntegrationFrame:
    """Call get_integration_frame."""
    return frame.get_integration_frame()
