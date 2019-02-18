"""
Support for Pocket Casts.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.pocketcasts/
"""
import logging

from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pocketcasts==0.1']

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:rss'

SENSOR_NAME = 'Pocketcasts unlistened episodes'

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the pocketcasts platform for sensors."""
    import pocketcasts

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    try:
        api = pocketcasts.Api(username, password)
        _LOGGER.debug("Found %d podcasts", len(api.my_podcasts()))
        add_entities([PocketCastsSensor(api)], True)
    except OSError as err:
        _LOGGER.error("Connection to server failed: %s", err)
        return False


class PocketCastsSensor(Entity):
    """Representation of a pocket casts sensor."""

    def __init__(self, api):
        """Initialize the sensor."""
        self._api = api
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return SENSOR_NAME

    @property
    def state(self):
        """Return the sensor state."""
        return self._state

    @property
    def icon(self):
        """Return the icon for the sensor."""
        return ICON

    def update(self):
        """Update sensor values."""
        try:
            self._state = len(self._api.new_episodes_released())
            _LOGGER.debug("Found %d new episodes", self._state)
        except OSError as err:
            _LOGGER.warning("Failed to contact server: %s", err)
