"""
Show the amount of records in a user's Discogs collection.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.discogs/
"""
from datetime import timedelta
import logging
import random

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

ICON_RECORD = 'mdi:album'
ICON_PLAYER = 'mdi:record-player'
UNIT_RECORDS = 'records'

SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Discogs sensor."""
    import discogs_client

    token = config[CONF_TOKEN]
    name = config[CONF_NAME]

    try:
        discogs_client = discogs_client.Client(
            SERVER_SOFTWARE, user_token=token)
        discogs_client.identity()
    except discogs_client.exceptions.HTTPError:
        _LOGGER.error("API token is not valid")
        return

    async_add_entities([
        DiscogsCollectionSensor(discogs_client, name),
        DiscogsWantlistSensor(discogs_client, name),
        DiscogsRandomRecordSensor(discogs_client, name),
    ], True)


class DiscogsCollectionSensor(Entity):
    """Get a user's number of records in collection."""

    def __init__(self, client, name):
        """Initialize the Discogs collection sensor."""
        self._client = client
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} Collection".format(self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON_RECORD

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return UNIT_RECORDS

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_IDENTITY: self._client.identity().name,
        }

    async def async_update(self):
        """Set state to the amount of records in user's collection."""
        self._state = self._client.identity().num_collection


class DiscogsWantlistSensor(Entity):
    """Get a user's number of records in wantlist."""

    def __init__(self, client, name):
        """Initialize the Discogs wantlist sensor."""
        self._client = client
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} Wantlist".format(self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON_RECORD

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return UNIT_RECORDS

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_IDENTITY: self._client.identity().name,
        }

    async def async_update(self):
        """Set state to the amount of records in user's collection."""
        self._state = self._client.identity().num_wantlist


class DiscogsRandomRecordSensor(Entity):
    """Suggest a random record from the user's collection."""

    def __init__(self, client, name):
        """Initialize the Discogs random record sensor."""
        self._client = client
        self._name = name
        self._state = None
        self._attrs = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} Random Record".format(self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON_PLAYER

    @property
    def device_state_attributes(self):
        """Return sensor attributes if data is available."""
        if self._state is None or self._attrs is None:
            return None

        return {
            'cat_no': self._attrs['labels'][0]['catno'],
            'cover_image': self._attrs['cover_image'],
            'format': "{} ({})".format(
                self._attrs['formats'][0]['name'],
                self._attrs['formats'][0]['descriptions'][0]),
            'label': self._attrs['labels'][0]['name'],
            'released': self._attrs['year'],
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_IDENTITY: self._client.identity().name,
        }

    async def async_update(self):
        """Set state to a random record in user's collection."""
        collection = self._client.identity().collection_folders[0]
        random_index = random.randrange(collection.count)
        random_record = collection.releases[random_index].release

        self._attrs = random_record.data
        self._state = "{} - {}".format(
            random_record.data['artists'][0]['name'],
            random_record.data['title'])
