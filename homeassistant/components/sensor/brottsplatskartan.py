"""
Sensor platform for Brottsplatskartan information.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.brottsplatskartan/
"""
from collections import defaultdict
from datetime import timedelta
import logging
import uuid

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['brottsplatskartan==0.0.1']

_LOGGER = logging.getLogger(__name__)

CONF_AREA = 'area'

DEFAULT_NAME = 'Brottsplatskartan'

SCAN_INTERVAL = timedelta(minutes=30)

AREAS = [
    "Blekinge län", "Dalarnas län", "Gotlands län", "Gävleborgs län",
    "Hallands län", "Jämtlands län", "Jönköpings län", "Kalmar län",
    "Kronobergs län", "Norrbottens län", "Skåne län", "Stockholms län",
    "Södermanlands län", "Uppsala län", "Värmlands län", "Västerbottens län",
    "Västernorrlands län", "Västmanlands län", "Västra Götalands län",
    "Örebro län", "Östergötlands län"
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Inclusive(CONF_LATITUDE, 'coordinates'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates'): cv.longitude,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_AREA, default=[]):
        vol.All(cv.ensure_list, [vol.In(AREAS)]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Brottsplatskartan platform."""
    import brottsplatskartan

    area = config.get(CONF_AREA)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    name = config.get(CONF_NAME)

    # Every Home Assistant instance should have their own unique
    # app parameter: https://brottsplatskartan.se/sida/api
    app = 'ha-{}'.format(uuid.getnode())

    bpk = brottsplatskartan.BrottsplatsKartan(
        app=app, area=area, latitude=latitude, longitude=longitude)

    add_entities([BrottsplatskartanSensor(bpk, name)], True)


class BrottsplatskartanSensor(Entity):
    """Representation of a Brottsplatskartan Sensor."""

    def __init__(self, bpk, name):
        """Initialize the Brottsplatskartan sensor."""
        import brottsplatskartan
        self._attributes = {ATTR_ATTRIBUTION: brottsplatskartan.ATTRIBUTION}
        self._brottsplatskartan = bpk
        self._name = name
        self._previous_incidents = set()
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

    def update(self):
        """Update device state."""
        incident_counts = defaultdict(int)
        incidents = self._brottsplatskartan.get_incidents()

        if incidents is False:
            _LOGGER.debug("Problems fetching incidents")
            return

        if len(incidents) < len(self._previous_incidents):
            self._previous_incidents = set()

        for incident in incidents:
            incident_type = incident.get('title_type')
            incident_counts[incident_type] += 1
            self._previous_incidents.add(incident.get('id'))

        self._attributes.update(incident_counts)
        self._state = len(incidents)
