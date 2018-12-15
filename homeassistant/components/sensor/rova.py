"""
Support for Rova garbage calendar.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rova/
"""

from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['rova==0.0.1']

# Config for rova requests.
CONF_ZIP_CODE = 'zip_code'
CONF_HOUSE_NUMBER = 'house_number'

UPDATE_DELAY = timedelta(hours=12)
SCAN_INTERVAL = timedelta(hours=12)

# Supported sensor types:
SENSOR_TYPES = {
    'gft': ['GFT', 'mdi:recycle'],
    'papier': ['Papier', 'mdi:recycle'],
    'plasticplus': ['PMD', 'mdi:recycle'],
    'rest': ['Rest', 'mdi:recycle']}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ZIP_CODE): cv.string,
    vol.Required(CONF_HOUSE_NUMBER): cv.string,
    vol.Optional(CONF_NAME, default='Rova'): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=['gft']):
    vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)])
})

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the Rova data service and sensors."""
    import rova.rova as r

    zip_code = config[CONF_ZIP_CODE]
    house_number = config[CONF_HOUSE_NUMBER]
    name = config[CONF_NAME]

    # Create new Rova object to  retrieve data
    api = r.Rova(zip_code, house_number)

    # Create rova data service which will retrieve and update the data.
    data = RovaData(hass, api)

    # Create a new sensor for each garbage type.
    entities = []
    for sensor_type in config[CONF_MONITORED_CONDITIONS]:
        sensor = RovaSensor(name, sensor_type, data)
        entities.append(sensor)

    add_entities(entities, True)


class RovaSensor(Entity):
    """Representation of a Rova sensor."""

    def __init__(self, sensor_name, sensor_type, data):
        """Initialize the sensor."""
        self.code = sensor_type
        self.sensor_name = sensor_name
        self.data = data

        self._state = None

    @property
    def name(self):
        """Return the name."""
        return "{}_{}".format(self.sensor_name, SENSOR_TYPES[self.code][0])

    @property
    def icon(self):
        """Return the sensor icon."""
        return SENSOR_TYPES[self.code][1]

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest data from the sensor and update the state."""
        self.data.update()
        pickup_date = self.data.data.get(self.code)
        if isinstance(pickup_date, datetime):
            self._state = pickup_date.isoformat()


class RovaData:
    """Get and update the latest data from the Rova API."""

    def __init__(self, hass, api):
        """Initialize the data object."""
        self.hass = hass
        self.api = api
        self.data = {}

    @Throttle(UPDATE_DELAY)
    def update(self):
        """Update the data from the Rova API."""
        from requests.exceptions import HTTPError, ConnectTimeout

        try:
            items = self.api.get_calendar_items()
        except (ConnectTimeout, HTTPError):
            _LOGGER.error("Could not retrieve data, retry again later")
            return

        _LOGGER.debug(items)

        self.data = {}

        for item in items:
            date = datetime.strptime(item['Date'], '%Y-%m-%dT%H:%M:%S')
            code = item['GarbageTypeCode'].lower()

            if code not in self.data and date > datetime.now():
                self.data[code] = date

        _LOGGER.debug("Updated Rova calendar: %s", self.data)
