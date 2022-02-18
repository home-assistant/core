"""Supervisor helper."""

import os

from homeassistant.core import callback


@callback
def is_hassio() -> bool:
    """Return true if on Hass.io."""
    return "HASSIO" in os.environ
