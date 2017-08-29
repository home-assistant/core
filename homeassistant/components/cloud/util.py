"""Utilities for the cloud integration."""
from .const import DOMAIN


def get_mode(hass):
    """Return the current mode of the cloud component.

    Async friendly.
    """
    return hass.data[DOMAIN]['mode']
