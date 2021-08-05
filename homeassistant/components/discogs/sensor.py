"""Show the amount of records in a user's Discogs collection."""
from datetime import timedelta
import logging
import random

import discogs_client
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_TOKEN,
)
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_IDENTITY = "identity"

ATTRIBUTION = "Data provided by Discogs"

DEFAULT_NAME = "Discogs"

ICON_RECORD = "mdi:album"
ICON_PLAYER = "mdi:record-player"
UNIT_RECORDS = "records"

SCAN_INTERVAL = timedelta(minutes=10)

SENSOR_COLLECTION_TYPE = "collection"
SENSOR_WANTLIST_TYPE = "wantlist"
SENSOR_RANDOM_RECORD_TYPE = "random_record"

SENSORS = {
    SENSOR_COLLECTION_TYPE: {
        "name": "Collection",
        "icon": ICON_RECORD,
        "unit_of_measurement": UNIT_RECORDS,
    },
    SENSOR_WANTLIST_TYPE: {
        "name": "Wantlist",
        "icon": ICON_RECORD,
        "unit_of_measurement": UNIT_RECORDS,
    },
    SENSOR_RANDOM_RECORD_TYPE: {
        "name": "Random Record",
        "icon": ICON_PLAYER,
        "unit_of_measurement": None,
    },
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSORS)): vol.All(
            cv.ensure_list, [vol.In(SENSORS)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Discogs sensor."""
    token = config[CONF_TOKEN]
    name = config[CONF_NAME]

    try:
        _discogs_client = discogs_client.Client(SERVER_SOFTWARE, user_token=token)

        discogs_data = {
            "user": _discogs_client.identity().name,
            "folders": _discogs_client.identity().collection_folders,
            "collection_count": _discogs_client.identity().num_collection,
            "wantlist_count": _discogs_client.identity().num_wantlist,
        }
    except discogs_client.exceptions.HTTPError:
        _LOGGER.error("API token is not valid")
        return

    sensors = []
    for sensor_type in config[CONF_MONITORED_CONDITIONS]:
        sensors.append(DiscogsSensor(discogs_data, name, sensor_type))

    add_entities(sensors, True)


class DiscogsSensor(SensorEntity):
    """Create a new Discogs sensor for a specific type."""

    def __init__(self, discogs_data, name, sensor_type):
        """Initialize the Discogs sensor."""
        self._discogs_data = discogs_data
        self._name = name
        self._type = sensor_type
        self._state = None
        self._attrs = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {SENSORS[self._type]['name']}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return SENSORS[self._type]["icon"]

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return SENSORS[self._type]["unit_of_measurement"]

    @property
    def extra_state_attributes(self):
        """Return the device state attributes of the sensor."""
        if self._state is None or self._attrs is None:
            return None

        if self._type == SENSOR_RANDOM_RECORD_TYPE and self._state is not None:
            return {
                "cat_no": self._attrs["labels"][0]["catno"],
                "cover_image": self._attrs["cover_image"],
                "format": f"{self._attrs['formats'][0]['name']} ({self._attrs['formats'][0]['descriptions'][0]})",
                "label": self._attrs["labels"][0]["name"],
                "released": self._attrs["year"],
                ATTR_ATTRIBUTION: ATTRIBUTION,
                ATTR_IDENTITY: self._discogs_data["user"],
            }

        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_IDENTITY: self._discogs_data["user"],
        }

    def get_random_record(self):
        """Get a random record suggestion from the user's collection."""
        # Index 0 in the folders is the 'All' folder
        collection = self._discogs_data["folders"][0]
        if collection.count > 0:
            random_index = random.randrange(collection.count)
            random_record = collection.releases[random_index].release

            self._attrs = random_record.data
            return f"{random_record.data['artists'][0]['name']} - {random_record.data['title']}"

        return None

    def update(self):
        """Set state to the amount of records in user's collection."""
        if self._type == SENSOR_COLLECTION_TYPE:
            self._state = self._discogs_data["collection_count"]
        elif self._type == SENSOR_WANTLIST_TYPE:
            self._state = self._discogs_data["wantlist_count"]
        else:
            self._state = self.get_random_record()
