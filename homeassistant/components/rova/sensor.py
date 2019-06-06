"""Support for Rova garbage calendar."""

from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_MONITORED_CONDITIONS, CONF_NAME,
                                 DEVICE_CLASS_TIMESTAMP)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

# Config for rova requests.
CONF_ZIP_CODE = 'zip_code'
CONF_HOUSE_NUMBER = 'house_number'
CONF_HOUSE_NUMBER_SUFFIX = 'house_number_suffix'

UPDATE_DELAY = timedelta(hours=12)
SCAN_INTERVAL = timedelta(hours=12)

# Supported sensor types:
# Key: [json_key, name, icon]
SENSOR_TYPES = {
    'bio': ['gft', 'Biowaste', 'mdi:recycle'],
    'paper': ['papier', 'Paper', 'mdi:recycle'],
    'plastic': ['plasticplus', 'PET', 'mdi:recycle'],
    'residual': ['rest', 'Residual', 'mdi:recycle']}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ZIP_CODE): cv.string,
    vol.Required(CONF_HOUSE_NUMBER): cv.string,
    vol.Optional(CONF_HOUSE_NUMBER_SUFFIX, default=''): cv.string,
    vol.Optional(CONF_NAME, default='Rova'): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=['bio']):
    vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)])
})

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the Rova data service and sensors."""
    from rova.rova import Rova
    from requests.exceptions import HTTPError, ConnectTimeout

    zip_code = config[CONF_ZIP_CODE]
    house_number = config[CONF_HOUSE_NUMBER]
    house_number_suffix = config[CONF_HOUSE_NUMBER_SUFFIX]
    platform_name = config[CONF_NAME]

    # Create new Rova object to  retrieve data
    api = Rova(zip_code, house_number, house_number_suffix)

    try:
        if not api.is_rova_area():
            _LOGGER.error("ROVA does not collect garbage in this area")
            return
    except (ConnectTimeout, HTTPError):
        _LOGGER.error("Could not retrieve details from ROVA API")
        return

    # Create rova data service which will retrieve and update the data.
    data_service = RovaData(api)

    # Create a new sensor for each garbage type.
    entities = []
    for sensor_key in config[CONF_MONITORED_CONDITIONS]:
        sensor = RovaSensor(platform_name, sensor_key, data_service)
        entities.append(sensor)

    add_entities(entities, True)


class RovaSensor(Entity):
    """Representation of a Rova sensor."""

    def __init__(self, platform_name, sensor_key, data_service):
        """Initialize the sensor."""
        self.sensor_key = sensor_key
        self.platform_name = platform_name
        self.data_service = data_service

        self._state = None

        self._json_key = SENSOR_TYPES[self.sensor_key][0]

    @property
    def name(self):
        """Return the name."""
        return "{}_{}".format(self.platform_name, self.sensor_key)

    @property
    def icon(self):
        """Return the sensor icon."""
        return SENSOR_TYPES[self.sensor_key][2]

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest data from the sensor and update the state."""
        self.data_service.update()
        pickup_date = self.data_service.data.get(self._json_key)
        if pickup_date is not None:
            self._state = pickup_date.isoformat()


class RovaData:
    """Get and update the latest data from the Rova API."""

    def __init__(self, api):
        """Initialize the data object."""
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

        self.data = {}

        for item in items:
            date = datetime.strptime(item['Date'], '%Y-%m-%dT%H:%M:%S')
            code = item['GarbageTypeCode'].lower()

            if code not in self.data and date > datetime.now():
                self.data[code] = date

        _LOGGER.debug("Updated Rova calendar: %s", self.data)
