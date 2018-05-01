"""
Support for Social Blade.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.socialblade/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['socialbladeclient==0.2']

CHANNEL_ID = 'channel_id'

DEFAULT_NAME = "Social Blade"

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=2)

SUBSCRIBERS = 'subscribers'

TOTAL_VIEWS = 'total_views'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CHANNEL_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Social Blade sensor."""
    social_blade = SocialBladeSensor(
        config[CHANNEL_ID], config[CONF_NAME])

    social_blade.update()
    if social_blade.valid_channel_id is False:
        return

    add_devices([social_blade])


class SocialBladeSensor(Entity):
    """Representation of a Social Blade Sensor."""

    def __init__(self, case, name):
        """Initialize the Social Blade sensor."""
        self._state = None
        self.channel_id = case
        self._attributes = None
        self.valid_channel_id = None
        self._name = name

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._attributes:
            return self._attributes

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Social Blade."""
        import socialbladeclient
        try:
            data = socialbladeclient.get_data(self.channel_id)
            self._attributes = {TOTAL_VIEWS: data[TOTAL_VIEWS]}
            self._state = data[SUBSCRIBERS]
            self.valid_channel_id = True

        except (ValueError, IndexError):
            _LOGGER.error("Unable to find valid channel ID")
            self.valid_channel_id = False
            self._attributes = None
