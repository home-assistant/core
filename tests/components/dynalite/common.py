"""Common functions for the Dynalite tests."""

from homeassistant.components import dynalite


def get_bridge_from_hass(hass_obj):
    """Get the bridge from hass.data."""
    key = next(iter(hass_obj.data[dynalite.DOMAIN]))
    return hass_obj.data[dynalite.DOMAIN][key]
