"""
Shows the amount of records in a user's Discogs collection.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.discogs/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_TOKEN)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:album'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
})

REQUIREMENTS = ['discogs_client==2.2.1']

SCAN_INTERVAL = timedelta(hours=2)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the discogs sensor."""
    token = config.get(CONF_TOKEN)

    async_add_devices([DiscogsCollection(token)], True)
    return True


class DiscogsCollection(Entity):
    """Get a user's number of records in collection."""

    def __init__(self, token):
        """Initialize the sensor."""
        import discogs_client
        discogs = discogs_client.Client(SERVER_SOFTWARE, user_token=token)

        self._ds_user = discogs.identity()
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Discogs'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return 'records'

    @asyncio.coroutine
    def async_update(self):
        """Set state to the amount of records in user's collection."""
        self._state = self._ds_user.num_collection
