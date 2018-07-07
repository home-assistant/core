"""
Support for Environment Canada weather.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/environment_canada/
"""
import logging

from homeassistant.helpers.discovery import load_platform

DOMAIN = 'environment_canada'

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Set up Environment Canada platforms."""
    load_platform(hass, 'sensor', DOMAIN)
    load_platform(hass, 'weather', DOMAIN)
    load_platform(hass, 'camera', DOMAIN)

    return True
