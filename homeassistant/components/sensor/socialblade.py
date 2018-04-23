"""
Support for Social Blade .

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.socialblade/
"""

import logging
from datetime import timedelta
import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_FRIENDLY_NAME


_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['socialbladeclient==0.2']

DEFAULT_NAME = "Social Blade"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_FRIENDLY_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required('channel_id'): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setting the platform in HASS and Channel Information."""
    social_blade = SocialBladeSensor(config['channel_id'], config[CONF_FRIENDLY_NAME])
    social_blade.update()
    if social_blade.valid_channel_id:
        add_devices([social_blade])
    else:
        _LOGGER.error("Setup Social Blade Sensor Fail"
                      " check if your channel ID is Valid")


class SocialBladeSensor(Entity):
    """Social Blade Sensor will check the subscribers / total views on
     givin youtube channel using the channel id."""

    HOURS_TO_UPDATE = timedelta(hours=2)

    SUBSCRIBERS = "subscribers"
    TOTAL_VIEWS = "total_views"

    def __init__(self, case, name):
        """Initialize the sensor."""
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
        return self._attributes

    @Throttle(HOURS_TO_UPDATE)
    def update(self):
        """Using Request to access SocialBlade website and fetch data."""
        import socialbladeclient
        try:
            data = socialbladeclient.get_data(self.channel_id)
            self._attributes = {
                self.TOTAL_VIEWS: data[self.TOTAL_VIEWS]
            }
            self._state = data[self.SUBSCRIBERS]
            self.valid_channel_id = True

        except ValueError:
            _LOGGER("Please Check that you have valid channel id")
            self.valid_channel_id = False
