"""
Support for IRC sensors.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/sensor.irc/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import STATE_UNKNOWN
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.irc import (
    CONF_NETWORK, CONF_CHANNEL, DATA_IRC)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['irc']

CONF_ATTRIBUTE = 'attribute'

ATTR_CHANNEL = 'channel'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CHANNEL): cv.string,
    vol.Required(CONF_NETWORK): cv.string,
    vol.Required(CONF_ATTRIBUTE): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the IRC sensor."""
    network = config.get(CONF_NETWORK)
    if network not in hass.data[DATA_IRC]:
        _LOGGER.error('Unknown IRC network: %s', network)
        return False

    network = config.get(CONF_NETWORK)
    channel = config.get(CONF_CHANNEL)
    attribute = config.get(CONF_ATTRIBUTE)
    plugin = hass.data[DATA_IRC][network]

    async_add_devices([IrcSensor(plugin.get_channel(channel), attribute)])


class IrcSensor(Entity):
    """Representation of an IRC sensor."""

    def __init__(self, channel, attribute):
        """Initialize the sensor."""
        self._channel = channel
        self._attribute = attribute

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Handle when an entity is about to be added to Home Assistant."""
        self._channel.observe(self)

    @property
    def should_poll(self):
        """No polling needed for IRC sensor."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{0} {1}'.format(self._channel.channel, self._attribute)

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._attribute == 'topic':
            return self._channel.topic
        elif self._attribute == 'last_speaker':
            return self._channel.last_speaker
        elif self._attribute == 'users':
            return len(self._channel.users)
        return STATE_UNKNOWN

    @callback
    def attr_updated(self, attr, value):
        """Callback when an attribute for a channel has changed."""
        if attr == self._attribute:
            self.hass.async_add_job(self.async_update_ha_state())

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_CHANNEL: self._channel.channel,
        }
