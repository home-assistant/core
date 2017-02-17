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
from homeassistant.components.zone import (
    ATTR_RADIUS, ENTITY_ID_FORMAT as ZONE_ENTITY_ID_FORMAT)
from homeassistant.const import (
    CONF_INCLUDE, CONF_EXCLUDE, CONF_ZONE,
    ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_FRIENDLY_NAME,
    LENGTH_KILOMETERS, LENGTH_METERS)
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from homeassistant.util.distance import convert
from homeassistant.util.dt import now
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['crimereports==1.0.0']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=30)
DEPENDENCIES = ['zone']
DOMAIN = 'crimereports'
EVENT_INCIDENT = '{}_incident'.format(DOMAIN)
NAME_FORMAT = '{} Incidents'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    CONF_ZONE: cv.string,
    vol.Optional(CONF_INCLUDE): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_EXCLUDE): vol.All(cv.ensure_list, [cv.string])
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Crime Reports platform."""
    zone_id = ZONE_ENTITY_ID_FORMAT.format(config.get(CONF_ZONE))
    zone_state = hass.states.get(zone_id)
    if not zone_state:
        _LOGGER.error("could not find specified zone: %s", zone_id)
        return
    latitude = zone_state.attributes.get(ATTR_LATITUDE)
    longitude = zone_state.attributes.get(ATTR_LONGITUDE)
    radius = zone_state.attributes.get(ATTR_RADIUS)
    zone_friendly_name = zone_state.attributes.get(ATTR_FRIENDLY_NAME)
    name = NAME_FORMAT.format(zone_friendly_name)
    add_devices([CrimeReportsSensor(hass, name, latitude, longitude, radius,
                                    config.get(CONF_INCLUDE),
                                    config.get(CONF_EXCLUDE))], True)


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
        self._crimereports = crimereports.CrimeReports((latitude, longitude),
                                                       radius_kilometers)
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
        incidents = self._crimereports.get_incidents(now().date(),
                                                     include=self._include,
                                                     exclude=self._exclude)
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
