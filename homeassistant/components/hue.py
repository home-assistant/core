"""
Support for Hue components.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/hue/
"""
import json
import logging

from homeassistant.const import (CONF_FILENAME)

_LOGGER = logging.getLogger(__name__)
PHUE_CONFIG_FILE = 'phue.conf'

DOMAIN = 'hue'


def load_conf(filepath):
    """Return the URL for API requests."""
    with open(filepath, 'r') as file_path:
        data = json.load(file_path)
        ip_add = next(data.keys().__iter__())
        username = data[ip_add]['username']
        url = 'http://' + ip_add + '/api/' + username
    return url


def setup(hass, config):
    """Set up the Hue component."""
    filename = config.get(CONF_FILENAME, PHUE_CONFIG_FILE)
    filepath = hass.config.path(filename)
    url = load_conf(filepath)
    hass.data[DOMAIN] = url
    return True
