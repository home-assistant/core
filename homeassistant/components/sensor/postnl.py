"""
Sensor for PostNL packages.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.postnl/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_NAME, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['postnl_api==1.0.2']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = 'Information provided by PostNL'

DEFAULT_NAME = 'postnl'

#ICONpackage = 'mdi:package-variant-closed'
#ICONletters = 'mdi:email-outline'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)

CONF_LETTER = 'letter'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_LETTER, default=False): cv.boolean
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the PostNL sensor platform."""
    from postnl_api import PostNL_API, UnauthorizedException

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    #name = config.get(CONF_NAME)
    letter = config.get(CONF_LETTER)

    try:
        api = PostNL_API(username, password)

    except UnauthorizedException:
        _LOGGER.exception("Can't connect to the PostNL webservice")
        return

    sensor_items = []
    sensor_items.extend([PostNLSensor(hass,
                                    'PostNL-package',
                                    'package-variant-closed',
                                    'packeges',
                                    api)])
									
    if letter:
        sensor_items.extend([PostNLSensor(hass,
                                        'PostNL-letter',
                                        'email-outline',
                                        'letters',
                                        api)])

    add_devices(sensor_items)


class PostNLSensor(Entity):
    """Representation of a PostNL sensor."""

    def __init__(self, hass, name, icon, unit_of_measurement, api):
        """Initialize the PostNL sensor."""
        self._name = name
        self._attributes = None
        self._state = None
        self._api = api
        self._icon = "mdi:" + icon
        self._unit_of_measurement = unit_of_measurement

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update device state."""
        shipments = self._api.get_relevant_shipments()
        status_counts = {}

        for shipment in shipments:
            status = shipment['status']['formatted']['short']
            status = self._api.parse_datetime(status, '%d-%m-%Y', '%H:%M')

            name = shipment['settings']['title']
            status_counts[name] = status

        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            **status_counts
        }

        self._state = 5
        # self._state = len(status_counts)		


        letters = self._api.get_relevant_letters()

        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

        self._state = 2
        # self._state = len(letters)
