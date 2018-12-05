"""Sensor for Brottsplatskartan."""
from collections import defaultdict
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['brottsplatskartan==0.0.1']

_LOGGER = logging.getLogger(__name__)

CONF_AREA = 'area'
DEFAULT_NAME = 'Brottsplatskartan'
DOMAIN = 'brottsplatskartan'
EVENT_INCIDENT = '{}_incident'.format(DOMAIN)
SCAN_INTERVAL = timedelta(minutes=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Inclusive(CONF_LATITUDE, 'coordinates'): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, 'coordinates'): cv.longitude,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_AREA, default=''): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Brottsplatskartan platform."""
    import brottsplatskartan
    import uuid
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    name = config.get(CONF_NAME)
    area = config.get(CONF_AREA)

    # Every Home Assistant instance should have their own unique
    # app parameter: https://brottsplatskartan.se/sida/api
    app = 'ha-' + str(uuid.getnode())

    bpk = brottsplatskartan.BrottsplatsKartan(
        app=app, area=area,
        latitude=latitude, longitude=longitude
    )

    add_entities(
        [BrottsplatskartanSensor(bpk, name)], True
    )


class BrottsplatskartanSensor(Entity):
    """Representation of a Brottsplatskartan Sensor."""

    def __init__(self, bpk, name):
        """Initialize the Brottsplatskartan sensor."""
        import brottsplatskartan
        self._attributes = {ATTR_ATTRIBUTION: brottsplatskartan.ATTRIBUTION}
        self._brottsplatskartan = bpk
        self._name = name
        self._previous_incidents = set()
        self._starting_up = True
        self._state = None

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
        """Fire if an event occurs."""
        data = {
            'description': incident.get('description'),
            'external_source_link': incident.get('external_source_link'),
            'location': incident.get('title_location'),
            'timestamp': incident.get('pubdate_iso8601'),
            'type': incident.get('title_type'),
        }

        if incident.get('lat') and incident.get('lng'):
            data.update(
                {
                    ATTR_LATITUDE: incident.get('lat'),
                    ATTR_LONGITUDE: incident.get('lng'),
                }
            )
        self.hass.bus.fire(EVENT_INCIDENT, data)

    def update(self):
        """Update device state."""
        incident_counts = defaultdict(int)
        incidents = self._brottsplatskartan.get_incidents()

        if incidents is False:
            _LOGGER.debug("Problems fetching incidents.")
            return

        if len(incidents) < len(self._previous_incidents):
            self._previous_incidents = set()

        for incident in incidents:
            incident_type = incident.get('title_type')
            incident_counts[incident_type] += 1

            current_incident_id = incident.get('id')
            if (
                    not self._starting_up
                    and current_incident_id not in self._previous_incidents
            ):
                self._incident_event(incident)
            self._previous_incidents.add(current_incident_id)

        self._attributes.update(incident_counts)
        self._starting_up = False
        self._state = len(incidents)
