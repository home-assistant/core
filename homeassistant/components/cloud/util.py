"""Cloud util functions."""

from hass_nabucasa import Cloud

from homeassistant.components import http
from homeassistant.core import HomeAssistant

from .client import CloudClient
from .const import DOMAIN


def get_strict_connection_mode(hass: HomeAssistant) -> http.const.StrictConnectionMode:
    """Get the strict connection mode."""
    cloud: Cloud[CloudClient] = hass.data[DOMAIN]
    return cloud.client.prefs.strict_connection
