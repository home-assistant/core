"""Support for transport.opendata.ch."""
from datetime import timedelta
import logging

from opendata_transport import OpendataTransport, OpendataTransportStationboard
from opendata_transport.exceptions import OpendataTransportError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_DEPARTURE_TIME1 = "next_departure"
ATTR_DEPARTURE_TIME2 = "next_on_departure"
ATTR_DURATION = "duration"
ATTR_PLATFORM = "platform"
ATTR_REMAINING_TIME = "remaining_time"
ATTR_START = "start"
ATTR_TARGET = "destination"
ATTR_TRAIN_NUMBER = "train_number"
ATTR_TRANSFERS = "transfers"
ATTR_DELAY = "delay"
ATTR_CONNECTIONS = "connections"
ATTR_DEPARTURES = "departures"

ATTRIBUTION = "Data provided by transport.opendata.ch"

CONF_DESTINATION = "to"
CONF_START = "from"
CONF_STATIONBOARD = "stationboard"
CONF_LIMIT = "limit"

DEFAULT_NAME = "Next Departure"

ICON = "mdi:bus"

SCAN_INTERVAL = timedelta(seconds=90)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DESTINATION): cv.string,
        vol.Optional(CONF_START): cv.string,
        vol.Optional(CONF_STATIONBOARD): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_LIMIT): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def test_opendata(opendata):
    """Test wheather the current configuration allows to get data."""

    try:
        data = await opendata.async_get_data()
        _LOGGER.debug(data)
    except OpendataTransportError:
        _LOGGER.error(
            "Check at http://transport.opendata.ch/examples/stationboard.html "
            "if your station names are valid"
        )
        return False
    return True


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Swiss public transport sensor."""

    name = config.get(CONF_NAME)
    start = config.get(CONF_START)
    destination = config.get(CONF_DESTINATION)
    stationboard = config.get(CONF_STATIONBOARD)
    limit = config.get(CONF_LIMIT, 5)

    session = async_get_clientsession(hass)

    entities = []

    if start is not None and destination is not None:
        opendata = OpendataTransport(start, destination, hass.loop, session, limit)
        if await test_opendata(opendata):
            entities.append(SwissPublicTransportSensor(opendata, name))

    if stationboard is not None:
        opendata = OpendataTransportStationboard(
            stationboard, hass.loop, session, limit
        )
        if await test_opendata(opendata):
            entities.append(SwissPublicTransportStationboardSensor(opendata, name))

    async_add_entities(entities)


class SwissPublicTransportStationboardSensor(Entity):
    """Implementation of an Swiss public transport stationboard sensor."""

    def __init__(self, opendata, name):
        """Initialize the sensor."""
        self._opendata = opendata
        self._name = name
        self._remaining_time = ""

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return (
            self._opendata.journeys[0]["departure"]
            if self._opendata is not None and len(self._opendata.journeys) > 0
            else None
        )

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._opendata is None or len(self._opendata.journeys) < 1:
            return

        self._remaining_time = dt_util.parse_datetime(
            self._opendata.journeys[0]["departure"]
        ) - dt_util.as_local(dt_util.utcnow())

        attr = {
            ATTR_DEPARTURES: self._opendata.journeys,
            ATTR_TRAIN_NUMBER: self._opendata.journeys[0]["number"],
            ATTR_PLATFORM: self._opendata.journeys[0]["platform"],
            ATTR_REMAINING_TIME: f"{self._remaining_time}",
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
        return attr

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    async def async_update(self):
        """Get the latest data from opendata.ch and update the states."""
        _LOGGER.info("async_update called")
        try:
            if self._remaining_time.total_seconds() < 0:
                self._opendata.journeys = []
                await self._opendata.async_get_data()
        except OpendataTransportError:
            _LOGGER.error("Unable to retrieve data from transport.opendata.ch")


class SwissPublicTransportSensor(Entity):
    """Implementation of an Swiss public transport sensor."""

    def __init__(self, opendata, name):
        """Initialize the sensor."""
        self._opendata = opendata
        self._name = name
        self._remaining_time = ""

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return (
            self._opendata.connections[0]["departure"]
            if self._opendata is not None
            else None
        )

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._opendata is None:
            return

        self._remaining_time = dt_util.parse_datetime(
            self._opendata.connections[0]["departure"]
        ) - dt_util.as_local(dt_util.utcnow())

        # Convert to a list since this is more approprate
        connections = [c[1] for c in sorted(self._opendata.connections.items())]

        attr = {
            ATTR_TRAIN_NUMBER: self._opendata.connections[0]["number"],
            ATTR_PLATFORM: self._opendata.connections[0]["platform"],
            ATTR_TRANSFERS: self._opendata.connections[0]["transfers"],
            ATTR_DURATION: self._opendata.connections[0]["duration"],
            ATTR_DEPARTURE_TIME1: self._opendata.connections[1]["departure"],
            ATTR_DEPARTURE_TIME2: self._opendata.connections[2]["departure"],
            ATTR_START: self._opendata.from_name,
            ATTR_TARGET: self._opendata.to_name,
            ATTR_REMAINING_TIME: f"{self._remaining_time}",
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_DELAY: self._opendata.connections[0]["delay"],
            ATTR_CONNECTIONS: connections,
        }
        return attr

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    async def async_update(self):
        """Get the latest data from opendata.ch and update the states."""

        try:
            if self._remaining_time.total_seconds() < 0:
                await self._opendata.async_get_data()
        except OpendataTransportError:
            _LOGGER.error("Unable to retrieve data from transport.opendata.ch")
