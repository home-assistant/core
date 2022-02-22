"""Supervisor helper."""

import os

from homeassistant.core import callback


@callback
def is_supervised() -> bool:
    """Return true if supervisor is available."""
    return "SUPERVISOR" in os.environ
