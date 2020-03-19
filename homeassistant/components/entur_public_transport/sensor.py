"""Real-time information about public transport departures in Norway."""
from datetime import datetime, timedelta
import logging

from enturclient import EnturPublicTransportData
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SHOW_ON_MAP,
    TIME_MINUTES,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

API_CLIENT_NAME = "homeassistant-homeassistant"

ATTRIBUTION = "Data provided by entur.org under NLOD"

CONF_STOP_IDS = "stop_ids"
CONF_EXPAND_PLATFORMS = "expand_platforms"
CONF_WHITELIST_LINES = "line_whitelist"
CONF_OMIT_NON_BOARDING = "omit_non_boarding"
CONF_NUMBER_OF_DEPARTURES = "number_of_departures"

DEFAULT_NAME = "Entur"
DEFAULT_ICON_KEY = "bus"

ICONS = {
    "air": "mdi:airplane",
    "bus": "mdi:bus",
    "metro": "mdi:subway",
    "rail": "mdi:train",
    "tram": "mdi:tram",
    "water": "mdi:ferry",
}

SCAN_INTERVAL = timedelta(seconds=45)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOP_IDS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_EXPAND_PLATFORMS, default=True): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SHOW_ON_MAP, default=False): cv.boolean,
        vol.Optional(CONF_WHITELIST_LINES, default=[]): cv.ensure_list,
        vol.Optional(CONF_OMIT_NON_BOARDING, default=True): cv.boolean,
        vol.Optional(CONF_NUMBER_OF_DEPARTURES, default=2): vol.All(
            cv.positive_int, vol.Range(min=2, max=10)
        ),
    }
)


ATTR_STOP_ID = "stop_id"

ATTR_ROUTE = "route"
ATTR_ROUTE_ID = "route_id"
ATTR_EXPECTED_AT = "due_at"
ATTR_DELAY = "delay"
ATTR_REALTIME = "real_time"

ATTR_NEXT_UP_IN = "next_due_in"
ATTR_NEXT_UP_ROUTE = "next_route"
ATTR_NEXT_UP_ROUTE_ID = "next_route_id"
ATTR_NEXT_UP_AT = "next_due_at"
ATTR_NEXT_UP_DELAY = "next_delay"
ATTR_NEXT_UP_REALTIME = "next_real_time"

ATTR_TRANSPORT_MODE = "transport_mode"


def due_in_minutes(timestamp: datetime) -> int:
    """Get the time in minutes from a timestamp."""
    if timestamp is None:
        return None
    diff = timestamp - dt_util.now()
    return int(diff.total_seconds() / 60)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Entur public transport sensor."""

    expand = config.get(CONF_EXPAND_PLATFORMS)
    line_whitelist = config.get(CONF_WHITELIST_LINES)
    name = config.get(CONF_NAME)
    show_on_map = config.get(CONF_SHOW_ON_MAP)
    stop_ids = config.get(CONF_STOP_IDS)
    omit_non_boarding = config.get(CONF_OMIT_NON_BOARDING)
    number_of_departures = config.get(CONF_NUMBER_OF_DEPARTURES)

    stops = [s for s in stop_ids if "StopPlace" in s]
    quays = [s for s in stop_ids if "Quay" in s]

    data = EnturPublicTransportData(
        API_CLIENT_NAME,
        stops=stops,
        quays=quays,
        line_whitelist=line_whitelist,
        omit_non_boarding=omit_non_boarding,
        number_of_departures=number_of_departures,
        web_session=async_get_clientsession(hass),
    )

    if expand:
        await data.expand_all_quays()
    await data.update()

    proxy = EnturProxy(data)

    entities = []
    for place in data.all_stop_places_quays():
        try:
            given_name = f"{name} {data.get_stop_info(place).name}"
        except KeyError:
            given_name = f"{name} {place}"

        entities.append(
            EnturPublicTransportSensor(proxy, given_name, place, show_on_map)
        )

    async_add_entities(entities, True)


class EnturProxy:
    """Proxy for the Entur client.

    Ensure throttle to not hit rate limiting on the API.
    """

    def __init__(self, api):
        """Initialize the proxy."""
        self._api = api

    @Throttle(timedelta(seconds=15))
    async def async_update(self) -> None:
        """Update data in client."""
        await self._api.update()

    def get_stop_info(self, stop_id: str) -> dict:
        """Get info about specific stop place."""
        return self._api.get_stop_info(stop_id)


class EnturPublicTransportSensor(Entity):
    """Implementation of a Entur public transport sensor."""

    def __init__(self, api: EnturProxy, name: str, stop: str, show_on_map: bool):
        """Initialize the sensor."""
        self.api = api
        self._stop = stop
        self._show_on_map = show_on_map
        self._name = name
        self._state = None
        self._icon = ICONS[DEFAULT_ICON_KEY]
        self._attributes = {}

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
        self._attributes[ATTR_ATTRIBUTION] = ATTRIBUTION
        self._attributes[ATTR_STOP_ID] = self._stop
        return self._attributes

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return TIME_MINUTES

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        return self._icon

    async def async_update(self) -> None:
        """Get the latest data and update the states."""
        await self.api.async_update()

        self._attributes = {}

        data = self.api.get_stop_info(self._stop)
        if data is None:
            self._state = None
            return

        if self._show_on_map and data.latitude and data.longitude:
            self._attributes[CONF_LATITUDE] = data.latitude
            self._attributes[CONF_LONGITUDE] = data.longitude

        calls = data.estimated_calls
        if not calls:
            self._state = None
            return

        self._state = due_in_minutes(calls[0].expected_departure_time)
        self._icon = ICONS.get(calls[0].transport_mode, ICONS[DEFAULT_ICON_KEY])

        self._attributes[ATTR_ROUTE] = calls[0].front_display
        self._attributes[ATTR_ROUTE_ID] = calls[0].line_id
        self._attributes[ATTR_EXPECTED_AT] = calls[0].expected_departure_time.strftime(
            "%H:%M"
        )
        self._attributes[ATTR_REALTIME] = calls[0].is_realtime
        self._attributes[ATTR_DELAY] = calls[0].delay_in_min

        number_of_calls = len(calls)
        if number_of_calls < 2:
            return

        self._attributes[ATTR_NEXT_UP_ROUTE] = calls[1].front_display
        self._attributes[ATTR_NEXT_UP_ROUTE_ID] = calls[1].line_id
        self._attributes[ATTR_NEXT_UP_AT] = calls[1].expected_departure_time.strftime(
            "%H:%M"
        )
        self._attributes[
            ATTR_NEXT_UP_IN
        ] = f"{due_in_minutes(calls[1].expected_departure_time)} min"
        self._attributes[ATTR_NEXT_UP_REALTIME] = calls[1].is_realtime
        self._attributes[ATTR_NEXT_UP_DELAY] = calls[1].delay_in_min

        if number_of_calls < 3:
            return

        for i, call in enumerate(calls[2:]):
            key_name = "departure_#" + str(i + 3)
            self._attributes[key_name] = (
                f"{'' if bool(call.is_realtime) else 'ca. '}"
                f"{call.expected_departure_time.strftime('%H:%M')} {call.front_display}"
            )
