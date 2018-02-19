"""
Sensor for Spot Crime.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.spotcrime/
"""

from datetime import timedelta
from collections import defaultdict
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_INCLUDE, CONF_EXCLUDE, CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE,
    ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE, CONF_RADIUS)
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['spotcrime==1.0.2']

_LOGGER = logging.getLogger(__name__)

CONF_DAYS = 'days'
DEFAULT_DAYS = 1

DOMAIN = 'spotcrime'

EVENT_INCIDENT = '{}_incident'.format(DOMAIN)

SCAN_INTERVAL = timedelta(minutes=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_RADIUS): vol.Coerce(float),
    vol.Inclusive(CONF_LATITUDE, 'coordinates'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates'): cv.longitude,
    vol.Optional(CONF_DAYS, default=DEFAULT_DAYS): cv.positive_int,
    vol.Optional(CONF_INCLUDE): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_EXCLUDE): vol.All(cv.ensure_list, [cv.string])
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Crime Reports platform."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    name = config.get(CONF_NAME)
    radius = config.get(CONF_RADIUS)
    days = config.get(CONF_DAYS)
    include = config.get(CONF_INCLUDE)
    exclude = config.get(CONF_EXCLUDE)

    add_devices([SpotCrimeSensor(
                hass, name, latitude, longitude, radius, include,
                exclude, days)], True)


class SpotCrimeSensor(Entity):
    """Representation of a Spot Crime Sensor."""

    def __init__(self, hass, name, latitude, longitude, radius,
                 include, exclude, days):
        """Initialize the Spot Crime sensor."""
        import spotcrime
        self._hass = hass
        self._name = name
        self._include = include
        self._exclude = exclude
        self.days = days
        self._spotcrime = spotcrime.SpotCrime(
            (latitude, longitude), radius, None, None, self.days)
        self._attributes = None
        self._state = None
        self._previous_incidents = set()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def _incident_event(self, incident):
        data = {
            'type': incident.get('type'),
            'timestamp': incident.get('timestamp'),
            'address': incident.get('location')
        }
        if incident.get('coordinates'):
            data.update({
                ATTR_LATITUDE: incident.get('lat'),
                ATTR_LONGITUDE: incident.get('lon')
            })
        self._hass.bus.fire(EVENT_INCIDENT, data)

    def update(self):
        """Update device state."""
        import spotcrime
        incident_counts = defaultdict(int)
        incidents = self._spotcrime.get_incidents()
        fire_events = len(self._previous_incidents) > 0
        if len(incidents) < len(self._previous_incidents):
            self._previous_incidents = set()
        for incident in incidents:
            incident_type = slugify(incident.get('type'))
            incident_counts[incident_type] += 1
            if (fire_events and incident.get('id')
                    not in self._previous_incidents):
                self._incident_event(incident)
            self._previous_incidents.add(incident.get('id'))
        self._attributes = {
            ATTR_ATTRIBUTION: spotcrime.ATTRIBUTION
        }
        self._attributes.update(incident_counts)
        self._state = len(incidents)
