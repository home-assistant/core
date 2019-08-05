"""The rmvtransport component."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_NAME,
    ATTR_ATTRIBUTION,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_ON_MAP,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import Throttle

# from .config_flow import configured_sensors, duplicate_stations
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    DEFAULT_TIMEOUT,
    DEFAULT_MAX_JOURNEYS,
    DEFAULT_TIME_OFFSET,
    CONF_STATION,
    CONF_DESTINATIONS,
    CONF_DIRECTION,
    CONF_LINES,
    CONF_PRODUCTS,
    CONF_TIME_OFFSET,
    CONF_MAX_JOURNEYS,
    CONF_TIMEOUT,
    VALID_PRODUCTS,
)

_LOGGER = logging.getLogger(__name__)

DATA_RMVTRANSPORT = "rmvtransport"
DATA_RMVTRANSPORT_CLIENT = "data_rmvtransport_client"
DATA_RMVTRANSPORT_LISTENER = "data_rmvtransport_listener"

TOPIC_UPDATE = "{0}_data_update".format(DOMAIN)

CONF_NEXT_DEPARTURE = "next_departure"

DEFAULT_NAME = "RMV Journey"

SCAN_INTERVAL = DEFAULT_SCAN_INTERVAL

ICONS = {
    "U-Bahn": "mdi:subway",
    "Tram": "mdi:tram",
    "Bus": "mdi:bus",
    "S": "mdi:train",
    "RB": "mdi:train",
    "RE": "mdi:train",
    "EC": "mdi:train",
    "IC": "mdi:train",
    "ICE": "mdi:train",
    "SEV": "mdi:checkbox-blank-circle-outline",
    None: "mdi:clock",
}

ATTRIBUTION = "Data provided by opendata.rmv.de"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NEXT_DEPARTURE): [
            {
                vol.Required(CONF_STATION): cv.string,
                vol.Optional(CONF_DESTINATIONS, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(CONF_DIRECTION): cv.string,
                vol.Optional(CONF_LINES, default=[]): vol.All(
                    cv.ensure_list, [cv.positive_int, cv.string]
                ),
                vol.Optional(CONF_PRODUCTS, default=VALID_PRODUCTS): vol.All(
                    cv.ensure_list, [vol.In(VALID_PRODUCTS)]
                ),
                vol.Optional(
                    CONF_TIME_OFFSET, default=DEFAULT_TIME_OFFSET
                ): cv.positive_int,
                vol.Optional(
                    CONF_MAX_JOURNEYS, default=DEFAULT_MAX_JOURNEYS
                ): cv.positive_int,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_SHOW_ON_MAP, default=False): cv.boolean,
            }
        ],
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                # vol.Required(CONF_STATION_ID): cv.string,
                vol.Required(CONF_STATION): cv.string,
                vol.Optional(CONF_DESTINATIONS, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(CONF_DIRECTION): cv.string,
                vol.Optional(CONF_LINES, default=[]): vol.All(
                    cv.ensure_list, [cv.positive_int, cv.string]
                ),
                vol.Optional(CONF_PRODUCTS, default=VALID_PRODUCTS): vol.All(
                    cv.ensure_list, [vol.In(VALID_PRODUCTS)]
                ),
                vol.Optional(
                    CONF_TIME_OFFSET, default=DEFAULT_TIME_OFFSET
                ): cv.positive_int,
                vol.Optional(
                    CONF_MAX_JOURNEYS, default=DEFAULT_MAX_JOURNEYS
                ): cv.positive_int,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_SHOW_ON_MAP, default=False): cv.boolean,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the RMV transport component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_RMVTRANSPORT_CLIENT] = {}
    hass.data[DOMAIN][DATA_RMVTRANSPORT_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_STATION: conf[CONF_STATION],
                CONF_SHOW_ON_MAP: conf[CONF_SHOW_ON_MAP],
            },
        )
    )

    hass.data[DOMAIN][CONF_SCAN_INTERVAL] = conf[CONF_SCAN_INTERVAL]

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Luftdaten as config entry."""
    from RMVtransport.rmvtransport import RMVtransportApiConnectionError

    session = async_get_clientsession(hass)

    try:
        rmv_rata = RMVDepartureData(
            session,
            config_entry.data[CONF_STATION],
            config_entry.data.get(CONF_DESTINATIONS, []),
            config_entry.data.get(CONF_DIRECTION),
            config_entry.data.get(CONF_LINES, []),
            config_entry.data.get(CONF_PRODUCTS, VALID_PRODUCTS),
            config_entry.data.get(CONF_TIME_OFFSET, DEFAULT_TIME_OFFSET),
            config_entry.data.get(CONF_MAX_JOURNEYS, DEFAULT_MAX_JOURNEYS),
            DEFAULT_TIMEOUT,
            config_entry.data.get(CONF_SHOW_ON_MAP, False),
        )
        await rmv_rata.async_update()
        hass.data[DOMAIN][DATA_RMVTRANSPORT_CLIENT][config_entry.entry_id] = rmv_rata
    except RMVtransportApiConnectionError:
        raise ConfigEntryNotReady

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )

    async def refresh_sensors(event_time):
        """Refresh RMV transport data."""
        await rmv_rata.async_update()
        async_dispatcher_send(hass, TOPIC_UPDATE)

    hass.data[DOMAIN][DATA_RMVTRANSPORT_LISTENER][
        config_entry.entry_id
    ] = async_track_time_interval(
        hass,
        refresh_sensors,
        hass.data[DOMAIN].get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an Luftdaten config entry."""
    remove_listener = hass.data[DOMAIN][DATA_RMVTRANSPORT_LISTENER].pop(
        config_entry.entry_id
    )
    remove_listener()

    for component in ("sensor",):
        await hass.config_entries.async_forward_entry_unload(config_entry, component)

    hass.data[DOMAIN][DATA_RMVTRANSPORT_CLIENT].pop(config_entry.entry_id)

    return True


class RMVDepartureData:
    """Pull data from the opendata.rmv.de web page."""

    def __init__(
        self,
        session,
        station_id,
        destinations,
        direction_id,
        lines,
        products,
        time_offset,
        max_journeys,
        timeout,
    ):
        """Initialize the sensor."""
        from RMVtransport import RMVtransport

        self.station = None
        self._station_id = station_id
        self._destinations = destinations
        self._direction_id = direction_id
        self._lines = lines
        self._products = products
        self._time_offset = time_offset
        self._max_journeys = max_journeys
        self.rmv = RMVtransport(session, timeout)
        self.departures = []
        self.station_info = None

    @Throttle(SCAN_INTERVAL)
    async def async_update(self):
        """Update the connection data."""
        from RMVtransport.rmvtransport import RMVtransportApiConnectionError

        if self.station_info is None:
            stations = await self.rmv.search_station(self._station_id)
            self.station_info = stations.get(str(self._station_id).zfill(9))

        try:
            _data = await self.rmv.get_departures(
                self._station_id,
                products=self._products,
                direction_id=self._direction_id,
                max_journeys=50,
            )
        except RMVtransportApiConnectionError:
            self.departures = []
            _LOGGER.warning("Could not retrive data from rmv.de")
            return
        self.station = _data.get("station")
        _deps = []
        for journey in _data["journeys"]:
            # find the first departure meeting the criteria
            _nextdep = {ATTR_ATTRIBUTION: ATTRIBUTION}
            if self._destinations:
                dest_found = False
                for dest in self._destinations:
                    if dest in journey["stops"]:
                        dest_found = True
                        _nextdep["destination"] = dest
                if not dest_found:
                    continue
            elif self._lines and journey["number"] not in self._lines:
                continue
            elif journey["minutes"] < self._time_offset:
                continue
            for attr in ["direction", "departure_time", "product", "minutes"]:
                _nextdep[attr] = journey.get(attr, "")
            _nextdep["line"] = journey.get("number", "")
            _deps.append(_nextdep)
            if len(_deps) > self._max_journeys:
                break
        self.departures = _deps
