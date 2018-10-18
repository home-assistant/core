"""
Real-time information about public transport departures in Norway.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.entur_public_transport/
"""
from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_LATITUDE,
    CONF_LONGITUDE, CONF_NAME, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['enturclient==0.1.0']

_LOGGER = logging.getLogger(__name__)

ATTR_EXPECTED_IN = 'due_in'
ATTR_NEXT_UP_IN = 'next_due_in'

API_CLIENT_ID = 'home-assistant'

CONF_ATTRIBUTION = "Data provided by entur.org under NLOD."
CONF_STOP_IDS = 'stop_ids'
CONF_EXPAND_PLATFORMS = 'expand_platforms'

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STOP_IDS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_EXPAND_PLATFORMS, default=True): cv.boolean,
})


def due_in_minutes(timestamp: str) -> str:
    """Get the time in minutes from a timestamp.

    The timestamp should be in the format
    year-month-yearThour:minute:second+timezone
    """
    if timestamp is None:
        return STATE_UNKNOWN
    diff = datetime.strptime(
        timestamp, "%Y-%m-%dT%H:%M:%S%z") - dt_util.now()

    return str(int(diff.total_seconds() / 60))


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Entur public transport sensor."""
    from enturclient import EnturPublicTransportData
    stop_ids = config.get(CONF_STOP_IDS)
    expand = config.get(CONF_EXPAND_PLATFORMS)

    stops = [s for s in stop_ids if "StopPlace" in s]
    quays = [s for s in stop_ids if "Quay" in s]

    data = EnturPublicTransportData(
        API_CLIENT_ID,
        stops,
        quays,
        expand)

    data.update()
    entities = []
    for item in data.all_stop_places_quays():
        entities.append(EnturPublicTransportSensor(EnturProxy(data), item))

    add_entities(entities, True)


class EnturProxy:
    """Proxy for the Entur client.

    Ensure throttle to not hit rate limiting on api.
    """

    def __init__(self, data):
        """Initialize the proxy."""
        self._data = data

    @Throttle(SCAN_INTERVAL)
    def update(self) -> None:
        """Update data in client."""
        self._data.update()

    def get_stop_info(self, stop_id: str) -> dict:
        """Get info about specific stop place."""
        return self._data.get_stop_info(stop_id)


class EnturPublicTransportSensor(Entity):
    """Implementation of a Entur public transport sensor."""

    def __init__(self, data: EnturProxy, stop: str):
        """Initialize the sensor."""
        self.data = data
        self._stop = stop
        self._times = data.get_stop_info(stop)
        self._state = STATE_UNKNOWN
        try:
            self._name = "Entur " + self._times[CONF_NAME]
        except TypeError:
            self._name = "Entur " + stop

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        from enturclient.consts import ATTR, ATTR_EXPECTED_AT
        try:
            return due_in_minutes(
                self._times[ATTR][ATTR_EXPECTED_AT])
        except TypeError:
            return STATE_UNKNOWN

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        from enturclient.consts import (
            CONF_LOCATION, ATTR, ATTR_NEXT_UP_AT,
            ATTR_STOP_ID, ATTR_EXPECTED_AT)
        if self._times is not None:
            attr = self._times[ATTR]
            attr[ATTR_NEXT_UP_IN] = due_in_minutes(attr[ATTR_NEXT_UP_AT])
            attr[ATTR_EXPECTED_IN] = due_in_minutes(attr[ATTR_EXPECTED_AT])
            attr[ATTR_STOP_ID] = self._times[ATTR_STOP_ID]
            attr[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
            if CONF_LOCATION in self._times:
                attr[CONF_LATITUDE] = \
                    self._times[CONF_LOCATION][CONF_LATITUDE]
                attr[CONF_LONGITUDE] = \
                    self._times[CONF_LOCATION][CONF_LONGITUDE]
            return attr

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return 'min'

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        from enturclient.consts import CONF_TRANSPORT_MODE
        if self._times[CONF_TRANSPORT_MODE] == 'bus':
            return 'mdi:bus'
        if self._times[CONF_TRANSPORT_MODE] == 'rail':
            return 'mdi:train'
        if self._times[CONF_TRANSPORT_MODE] == 'water':
            return 'mdi:ferry'
        if self._times[CONF_TRANSPORT_MODE] == 'air':
            return 'mdi:airplane'

        return 'mdi:bus'

    def update(self) -> None:
        """Get the latest data and update the states."""
        self.data.update()
        self._times = self.data.get_stop_info(self._stop)
