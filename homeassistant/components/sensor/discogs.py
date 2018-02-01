"""
Show the amount of records in a user's Discogs collection.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.discogs/
"""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['discogs_client==2.2.1']

_LOGGER = logging.getLogger(__name__)

ATTR_IDENTITY = 'identity'

CONF_ATTRIBUTION = "Data provided by Discogs"

DEFAULT_NAME = 'Discogs'

ICON = 'mdi:album'

SCAN_INTERVAL = timedelta(hours=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Discogs sensor."""
    import discogs_client

    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)

    try:
        discogs = discogs_client.Client(SERVER_SOFTWARE, user_token=token)
        identity = discogs.identity()
    except discogs_client.exceptions.HTTPError:
        _LOGGER.error("API token is not valid")
        return

    async_add_devices([DiscogsSensor(identity, name)], True)


class DiscogsSensor(Entity):
    """Get a user's number of records in collection."""

    def __init__(self, identity, name):
        """Initialize the Discogs sensor."""
        self._identity = identity
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

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

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_IDENTITY: self._identity.name,
        }

    @asyncio.coroutine
    def async_update(self):
        """Set state to the amount of records in user's collection."""
        self._state = self._identity.num_collection
