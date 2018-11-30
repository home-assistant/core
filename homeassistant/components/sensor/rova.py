"""
Support for Rova garbage calendar.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rova/
"""

import asyncio
from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.light import PLATFORM_SCHEMA
from homeassistant.const import CONF_MONITORED_VARIABLES
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

REQUIREMENTS = ['rova==0.0.1']

DOMAIN = 'rova'

# Config for rova requests.
CONF_ZIP_CODE = 'zip_code'
CONF_HOUSE_NUMBER = 'house_number'

# Supported sensor types:
SENSOR_TYPES = {
    'gft': ['GFT', 'mdi:recycle'],
    'papier': ['Papier', 'mdi:recycle'],
    'plasticplus': ['PMD', 'mdi:recycle'],
    'rest': ['Rest', 'mdi:recycle']}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ZIP_CODE): cv.string,
    vol.Required(CONF_HOUSE_NUMBER): cv.string,
    vol.Optional(CONF_MONITORED_VARIABLES, default=[]):
    vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)])
})

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Create the Rova data service and sensors."""
    zip_code = config.get(CONF_ZIP_CODE, None)
    house_number = config.get(CONF_HOUSE_NUMBER, None)

    # Create rova data service which will retrieve and update the data.
    data = RovaData(hass, zip_code, house_number)

    # Create a new sensor for each garbage type.
    entities = []
    for sensor_type in config[CONF_MONITORED_VARIABLES]:
        sensor = RovaSensor(sensor_type, data)
        entities.append(sensor)

    async_add_entities(entities, True)

    # Schedule first data service update straight away.
    async_track_point_in_utc_time(hass, data.async_update, dt_util.utcnow())


class RovaSensor(Entity):
    """Representation of a Rova sensor."""

    def __init__(self, sensor_type, data):
        """Initialize the sensor."""
        self.code = sensor_type
        self.data = data

    @property
    def name(self):
        """Return the name."""
        return 'rova_garbage_' + SENSOR_TYPES[self.code][0]

    @property
    def icon(self):
        """Return the sensor icon."""
        return SENSOR_TYPES[self.code][1]

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.code in self.data.data:
            return self.data.data.get(self.code).isoformat()
        return 0


class RovaData:
    """Get and update the latest data from the Rova API."""

    def __init__(self, hass, zip_code, house_number):
        """Initialize the data object."""
        self.hass = hass
        self.zip_code = zip_code
        self.house_number = house_number
        self.data = {}

    @asyncio.coroutine
    def schedule_update(self):
        """Schedule an update for the next day."""
        nxt = dt_util.utcnow() + timedelta(days=1)
        _LOGGER.debug("Scheduling next Rova update in 1 day")
        async_track_point_in_utc_time(self.hass, self.async_update, nxt)

    @asyncio.coroutine
    def async_update(self, *_):
        """Update the data from the Rova API."""
        import rova.rova as r
        from requests.exceptions import HTTPError, ConnectTimeout

        # Create new Rova object to  retrieve data
        api = r.Rova(self.zip_code, self.house_number)

        try:
            items = api.get_calendar_items()
        except (ConnectTimeout, HTTPError):
            _LOGGER.debug("Could not retrieve data, retry again tomorrow")
            yield from self.schedule_update()
            return

        _LOGGER.debug(items)

        self.data = {}

        for item in items:
            date = datetime.strptime(item['Date'], '%Y-%m-%dT%H:%M:%S')
            code = item['GarbageTypeCode'].lower()

            if code not in self.data and date > datetime.now():
                self.data[code] = date

        _LOGGER.debug("Updated Rova calendar: %s", self.data)

        yield from self.schedule_update()
        return
