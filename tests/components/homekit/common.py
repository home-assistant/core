"""Collection of fixtures and functions for the HomeKit tests."""
from unittest.mock import patch


def patch_debounce():
    """Return patch for debounce method."""
    return patch('homeassistant.components.homekit.accessories.debounce',
                 lambda f: lambda *args, **kwargs: f(*args, **kwargs))
