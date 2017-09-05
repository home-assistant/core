"""
Support for tracking a user on IRC.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.irc/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, SOURCE_TYPE_OTHER)
from homeassistant.components.irc import (
    CONF_NETWORK, CONF_CHANNEL, DATA_IRC)
from homeassistant.core import callback
from homeassistant.util import slugify
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['irc']

_LOGGER = logging.getLogger(__name__)

CONF_USER = 'user'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NETWORK): cv.string,
    vol.Required(CONF_USER): cv.string,
    vol.Required(CONF_CHANNEL): cv.string,
})


@asyncio.coroutine
def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Validate the configuration and setup monitoring of a user."""
    network = config.get(CONF_NETWORK)
    if network not in hass.data[DATA_IRC]:
        _LOGGER.error('Unknown IRC network: %s', network)
        return False

    user = config.get(CONF_USER)
    channel = config.get(CONF_CHANNEL)
    plugin = hass.data[DATA_IRC][network]

    class ChannelUserObserver:
        """Monitor changes to a channel."""

        @callback
        @staticmethod
        def attr_updated(attr, value):
            """Callback when an attribute for a channel has changed."""
            if attr != 'users':
                return

            dev_id = slugify('{0} {1}'.format(user, channel))
            status = 'online' if user in value else 'offline'
            hass.async_add_job(
                async_see(dev_id=dev_id,
                          location_name=status,
                          source_type=SOURCE_TYPE_OTHER))

    chan = plugin.get_channel(channel)
    chan.observe(ChannelUserObserver())

    return True
