"""Sensor for PostNL packages."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Information provided by PostNL"

DEFAULT_NAME = "postnl"

ICON = "mdi:package-variant-closed"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the PostNL sensor platform."""
    from postnl_api import PostNL_API, UnauthorizedException

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    name = config.get(CONF_NAME)

    try:
        api = PostNL_API(username, password)
        _LOGGER.debug("Connection with PostNL API succeeded")

    except UnauthorizedException:
        _LOGGER.exception("Can't connect to the PostNL webservice")
        return

    add_entities([PostNLDelivery(api, name)], True)
    add_entities([PostNLDistribution(api, name)], True)
    add_entities([PostNLLetter(api, name)], True)


class PostNLDelivery(Entity):
    """Delivery Packages."""

    def __init__(self, api, name):
        """Initialize the PostNL sensor."""
        self._name = name + "_delivery"
        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            'enroute': [],
            'delivered': [],
        }
        self._state = None
        self._api = api

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
        return 'packages'

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:package-variant-closed"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update device state."""
        shipments = self._api.get_deliveries()

        self._attributes['enroute'] = []
        self._attributes['delivered'] = []

        for shipment in shipments:
            if shipment.delivery_date is None:
                self._attributes['enroute'].append(vars(shipment))
            else:
                self._attributes['delivered'].append(vars(shipment))

        self._state = len(self._attributes['enroute'])


class PostNLDistribution(Entity):
    """Distribution Packages."""

    def __init__(self, api, name):
        """Initialize the PostNL sensor."""
        self._name = name + "_distribution"
        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            'enroute': [],
            'delivered': [],
        }
        self._state = None
        self._api = api

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
        return 'packages'

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:package-variant-closed"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update device state."""
        shipments = self._api.get_distributions()

        self._attributes['enroute'] = []
        self._attributes['delivered'] = []

        for shipment in shipments:
            if shipment.delivery_date is None:
                self._attributes['enroute'].append(vars(shipment))
            else:
                self._attributes['delivered'].append(vars(shipment))

        self._state = len(self._attributes['enroute'])


class PostNLLetter(Entity):
    """Letters."""

    def __init__(self, api, name):
        """Initialize the PostNL sensor."""
        self._name = name + "_letters"
        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            'letters': [],
            'enabled': False,
        }
        self._state = None
        self._api = api

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
        return 'letters'

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:email"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update device state."""
        self._attributes['enabled'] = self._api.is_letters_activated

        if self._attributes['enabled']:
            letters = self._api.get_letters()

            self._attributes['letters'] = []

            for letter in letters:
                self._attributes['letters'].append(vars(letter))
            self._state = len(letters)
