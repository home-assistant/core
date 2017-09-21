"""
Sensor for Crime Reports.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.crimereports/
"""
from collections import defaultdict
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_INCLUDE, CONF_EXCLUDE, CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE,
    ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE,
    LENGTH_KILOMETERS, LENGTH_METERS)
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from homeassistant.util.distance import convert
from homeassistant.util.dt import now
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['crimereports==1.0.0']

_LOGGER = logging.getLogger(__name__)

CONF_RADIUS = 'radius'

DOMAIN = 'crimereports'

EVENT_INCIDENT = '{}_incident'.format(DOMAIN)

SCAN_INTERVAL = timedelta(minutes=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_RADIUS): vol.Coerce(float),
    vol.Inclusive(CONF_LATITUDE, 'coordinates'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates'): cv.longitude,
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
    include = config.get(CONF_INCLUDE)
    exclude = config.get(CONF_EXCLUDE)

    add_devices([CrimeReportsSensor(
        hass, name, latitude, longitude, radius, include, exclude)], True)


class CrimeReportsSensor(Entity):
    """Crime Reports Sensor."""

    def __init__(self, hass, name, latitude, longitude, radius,
                 include, exclude):
        """Initialize the sensor."""
        import crimereports
        self._hass = hass
        self._name = name
        self._include = include
        self._exclude = exclude
        radius_kilometers = convert(radius, LENGTH_METERS, LENGTH_KILOMETERS)
        self._crimereports = crimereports.CrimeReports(
            (latitude, longitude), radius_kilometers)
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
            'description': incident.get('friendly_description'),
            'timestamp': incident.get('timestamp'),
            'location': incident.get('location')
        }
        if incident.get('coordinates'):
            data.update({
                ATTR_LATITUDE: incident.get('coordinates')[0],
                ATTR_LONGITUDE: incident.get('coordinates')[1]
            })
        self._hass.bus.fire(EVENT_INCIDENT, data)

    def update(self):
        """Update device state."""
        import crimereports
        incident_counts = defaultdict(int)
        incidents = self._crimereports.get_incidents(
            now().date(), include=self._include, exclude=self._exclude)
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
            ATTR_ATTRIBUTION: crimereports.ATTRIBUTION
        }
        self._attributes.update(incident_counts)
        self._state = len(incidents)
