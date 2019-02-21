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
    ATTR_ATTRIBUTION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME,
    CONF_SHOW_ON_MAP)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['enturclient==0.1.3']

_LOGGER = logging.getLogger(__name__)

ATTR_NEXT_UP_IN = 'next_due_in'

API_CLIENT_NAME = 'homeassistant-homeassistant'

ATTRIBUTION = "Data provided by entur.org under NLOD"

CONF_STOP_IDS = 'stop_ids'
CONF_EXPAND_PLATFORMS = 'expand_platforms'
CONF_WHITELIST_LINES = 'line_whitelist'

DEFAULT_NAME = 'Entur'
DEFAULT_ICON_KEY = 'bus'

ICONS = {
    'air': 'mdi:airplane',
    'bus': 'mdi:bus',
    'metro': 'mdi:subway',
    'rail': 'mdi:train',
    'tram': 'mdi:tram',
    'water': 'mdi:ferry',
}

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STOP_IDS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_EXPAND_PLATFORMS, default=True): cv.boolean,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SHOW_ON_MAP, default=False): cv.boolean,
    vol.Optional(CONF_WHITELIST_LINES, default=[]): cv.ensure_list,
})


def due_in_minutes(timestamp: str) -> str:
    """Get the time in minutes from a timestamp.

    The timestamp should be in the format
    year-month-yearThour:minute:second+timezone
    """
    if timestamp is None:
        return None
    diff = datetime.strptime(
        timestamp, "%Y-%m-%dT%H:%M:%S%z") - dt_util.now()

    return str(int(diff.total_seconds() / 60))


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Entur public transport sensor."""
    from enturclient import EnturPublicTransportData
    from enturclient.consts import CONF_NAME as API_NAME

    expand = config.get(CONF_EXPAND_PLATFORMS)
    line_whitelist = config.get(CONF_WHITELIST_LINES)
    name = config.get(CONF_NAME)
    show_on_map = config.get(CONF_SHOW_ON_MAP)
    stop_ids = config.get(CONF_STOP_IDS)

    stops = [s for s in stop_ids if "StopPlace" in s]
    quays = [s for s in stop_ids if "Quay" in s]

    data = EnturPublicTransportData(API_CLIENT_NAME,
                                    stops,
                                    quays,
                                    expand,
                                    line_whitelist)
    data.update()

    proxy = EnturProxy(data)

    entities = []
    for item in data.all_stop_places_quays():
        try:
            given_name = "{} {}".format(
                name, data.get_stop_info(item)[API_NAME])
        except KeyError:
            given_name = "{} {}".format(name, item)

        entities.append(
            EnturPublicTransportSensor(proxy, given_name, item, show_on_map))

    add_entities(entities, True)


class EnturProxy:
    """Proxy for the Entur client.

    Ensure throttle to not hit rate limiting on the API.
    """

    def __init__(self, api):
        """Initialize the proxy."""
        self._api = api

    @Throttle(SCAN_INTERVAL)
    def update(self) -> None:
        """Update data in client."""
        self._api.update()

    def get_stop_info(self, stop_id: str) -> dict:
        """Get info about specific stop place."""
        return self._api.get_stop_info(stop_id)


class EnturPublicTransportSensor(Entity):
    """Implementation of a Entur public transport sensor."""

    def __init__(
            self, api: EnturProxy, name: str, stop: str, show_on_map: bool):
        """Initialize the sensor."""
        from enturclient.consts import ATTR_STOP_ID

        self.api = api
        self._stop = stop
        self._show_on_map = show_on_map
        self._name = name
        self._state = None
        self._icon = ICONS[DEFAULT_ICON_KEY]
        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STOP_ID: self._stop,
        }

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attributes

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return 'min'

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        return self._icon

    def update(self) -> None:
        """Get the latest data and update the states."""
        from enturclient.consts import (
            ATTR, ATTR_EXPECTED_AT, ATTR_NEXT_UP_AT, CONF_LOCATION,
            CONF_LATITUDE as LAT, CONF_LONGITUDE as LONG, CONF_TRANSPORT_MODE)

        self.api.update()

        data = self.api.get_stop_info(self._stop)
        if data is not None and ATTR in data:
            attrs = data[ATTR]
            self._attributes.update(attrs)

            if ATTR_NEXT_UP_AT in attrs:
                self._attributes[ATTR_NEXT_UP_IN] = \
                    due_in_minutes(attrs[ATTR_NEXT_UP_AT])

            if CONF_LOCATION in data and self._show_on_map:
                self._attributes[CONF_LATITUDE] = data[CONF_LOCATION][LAT]
                self._attributes[CONF_LONGITUDE] = data[CONF_LOCATION][LONG]

            if ATTR_EXPECTED_AT in attrs:
                self._state = due_in_minutes(attrs[ATTR_EXPECTED_AT])
            else:
                self._state = None

            self._icon = ICONS.get(
                data[CONF_TRANSPORT_MODE], ICONS[DEFAULT_ICON_KEY])
        else:
            self._state = None
