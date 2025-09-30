"""Sensor for the CityBikes data."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import typing

import aiohttp
import voluptuous as vol

from homeassistant.components.sensor import ENTITY_ID_FORMAT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ID,
    ATTR_LATITUDE,
    ATTR_LOCATION,
    ATTR_LONGITUDE,
    ATTR_NAME,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import location as location_util
from homeassistant.util.unit_conversion import DistanceConverter
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

_LOGGER = logging.getLogger(__name__)

ATTR_COUNTRY = "country"
ATTR_CITY = "city"
ATTR_EMPTY_SLOTS = "empty_slots"
ATTR_EXTRA = "extra"
ATTR_FREE_BIKES = "free_bikes"
ATTR_NETWORK = "network"
ATTR_NETWORKS_LIST = "networks"
ATTR_STATIONS_LIST = "stations"
ATTR_TIMESTAMP = "timestamp"
ATTR_UID = "uid"

CONF_NETWORK = "network"
CONF_STATIONS_LIST = "stations"

DEFAULT_ENDPOINT = "https://api.citybik.es/{uri}"
PLATFORM = "citybikes"

MONITORED_NETWORKS = "monitored-networks"

NETWORKS_URI = "v2/networks"

REQUEST_TIMEOUT = 5  # In seconds; argument to asyncio.timeout

SCAN_INTERVAL = timedelta(minutes=5)  # Timely, and doesn't suffocate the API

STATIONS_URI = "v2/networks/{uid}?fields=network.stations"

CITYBIKES_ATTRIBUTION = (
    "Information provided by the CityBikes Project (https://citybik.es/#about)"
)

CITYBIKES_NETWORKS = "citybikes_networks"

NETWORK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_LOCATION): vol.Schema(
            {
                vol.Required(ATTR_LATITUDE): cv.latitude,
                vol.Required(ATTR_LONGITUDE): cv.longitude,
                vol.Required(ATTR_CITY): vol.Any(str, None),
                vol.Required(ATTR_COUNTRY): vol.Any(str, None),
            },
            extra=vol.REMOVE_EXTRA,
        ),
    },
    extra=vol.REMOVE_EXTRA,
)

NETWORKS_RESPONSE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_NETWORKS_LIST): [NETWORK_SCHEMA]}
)

STATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_FREE_BIKES): cv.positive_int,
        vol.Required(ATTR_EMPTY_SLOTS): vol.Any(cv.positive_int, None),
        vol.Required(ATTR_LATITUDE): cv.latitude,
        vol.Required(ATTR_LONGITUDE): cv.longitude,
        vol.Required(ATTR_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_TIMESTAMP): cv.string,
        vol.Optional(ATTR_EXTRA): vol.Schema(
            {vol.Optional(ATTR_UID): cv.string}, extra=vol.REMOVE_EXTRA
        ),
    },
    extra=vol.REMOVE_EXTRA,
)

STATIONS_RESPONSE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NETWORK): vol.Schema(
            {vol.Required(ATTR_STATIONS_LIST): [STATION_SCHEMA]}, extra=vol.REMOVE_EXTRA
        )
    }
)


class CityBikesRequestError(Exception):
    """Error to indicate a CityBikes API request has failed."""


async def async_citybikes_request(
    hass: HomeAssistant,
    uri: str,
    schema: vol.Schema,
    session: aiohttp.ClientSession | None = None,
):
    """Perform a request to CityBikes API endpoint, and parse the response."""
    try:
        if session is None:
            session = async_get_clientsession(hass)

        async with asyncio.timeout(REQUEST_TIMEOUT):
            req = await session.get(DEFAULT_ENDPOINT.format(uri=uri))

        json_response = await req.json()
        return schema(json_response)
    except (TimeoutError, aiohttp.ClientError):
        _LOGGER.error("Could not connect to CityBikes API endpoint")
    except ValueError:
        _LOGGER.error("Received non-JSON data from CityBikes API endpoint")
    except vol.Invalid as err:
        _LOGGER.error("Received unexpected JSON from CityBikes API endpoint: %s", err)
    raise CityBikesRequestError


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the CityBikes platform."""
    if PLATFORM not in hass.data:
        hass.data[PLATFORM] = {MONITORED_NETWORKS: {}}

    latitude = config_entry.data.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config_entry.data.get(CONF_LONGITUDE, hass.config.longitude)
    network_id = config_entry.data[CONF_NETWORK]
    stations_list = set(config_entry.data.get(CONF_STATIONS_LIST, []))
    radius = config_entry.data.get(CONF_RADIUS, 0)
    name = config_entry.data.get(CONF_NAME)
    if hass.config.units is US_CUSTOMARY_SYSTEM:
        radius = DistanceConverter.convert(
            radius, UnitOfLength.FEET, UnitOfLength.METERS
        )

    if network_id not in hass.data[PLATFORM][MONITORED_NETWORKS]:
        network = CityBikesNetwork(hass, network_id)
        hass.data[PLATFORM][MONITORED_NETWORKS][network_id] = network
        hass.async_create_task(network.async_refresh())
        async_track_time_interval(hass, network.async_refresh, SCAN_INTERVAL)
    else:
        network = hass.data[PLATFORM][MONITORED_NETWORKS][network_id]

    await network.ready.wait()

    entities: list[CityBikesStation] = []
    for station in network.stations:
        dist = location_util.distance(
            latitude, longitude, station[ATTR_LATITUDE], station[ATTR_LONGITUDE]
        )
        station_id = station[ATTR_ID]
        station_uid = str(station.get(ATTR_EXTRA, {}).get(ATTR_UID, ""))

        if dist is not None and (
            radius > dist or stations_list.intersection((station_id, station_uid))
        ):
            if name:
                uid = f"{network.network_id}_{name}_{station_id}"
            else:
                uid = f"{network.network_id}_{station_id}"
            entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, uid, hass=hass)
            entities.append(CityBikesStation(network, station_id, entity_id))

    async_add_entities(entities, True)


class CityBikesNetworks:
    """Represent all CityBikes networks."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the networks instance."""
        self.hass = hass
        self.networks = None
        self.networks_loading = asyncio.Condition()
        self.session: aiohttp.ClientSession | None = None

    async def load_networks(self, session: aiohttp.ClientSession | None = None):
        """Load the list of networks from the CityBikes API."""
        try:
            await self.networks_loading.acquire()
            if self.networks is None:
                networks = await async_citybikes_request(
                    self.hass,
                    NETWORKS_URI,
                    NETWORKS_RESPONSE_SCHEMA,
                    session=session or self.session,
                )
                self.networks = networks[ATTR_NETWORKS_LIST]
        except CityBikesRequestError as err:
            raise PlatformNotReady from err
        finally:
            self.networks_loading.release()
        return self.networks

    async def get_closest_network_id(self, latitude, longitude):
        """Return the id of the network closest to provided location."""
        await self.load_networks()
        if self.networks is None:
            raise PlatformNotReady
        result = None
        minimum_dist = None
        for network in self.networks:
            network_latitude = network[ATTR_LOCATION][ATTR_LATITUDE]
            network_longitude = network[ATTR_LOCATION][ATTR_LONGITUDE]
            dist = location_util.distance(
                latitude, longitude, network_latitude, network_longitude
            )
            if dist is not None and (minimum_dist is None or dist < minimum_dist):
                minimum_dist = dist
                result = network[ATTR_ID]
        return result


class CityBikesNetwork:
    """Thin wrapper around a CityBikes network object."""

    def __init__(self, hass: HomeAssistant, network_id: str) -> None:
        """Initialize the network object."""
        self.hass = hass
        self.network_id = network_id
        self.stations: list[dict[str, typing.Any]] = []
        self.ready = asyncio.Event()

    async def async_refresh(self, now=None) -> None:
        """Refresh the state of the network."""
        _LOGGER.debug("Refreshing CityBikes network %s", self.network_id)
        try:
            network = await async_citybikes_request(
                self.hass,
                STATIONS_URI.format(uid=self.network_id),
                STATIONS_RESPONSE_SCHEMA,
            )
            self.stations = network[ATTR_NETWORK][ATTR_STATIONS_LIST]
            self.ready.set()
        except CityBikesRequestError as err:
            if now is not None:
                self.ready.clear()
            else:
                raise PlatformNotReady from err


class CityBikesStation(SensorEntity):
    """CityBikes API Sensor."""

    _attr_attribution = CITYBIKES_ATTRIBUTION
    _attr_native_unit_of_measurement = "bikes"
    _attr_icon = "mdi:bike"

    def __init__(self, network, station_id, entity_id) -> None:
        """Initialize the sensor."""
        self._network = network
        self._station_id = station_id
        self.entity_id = entity_id

    async def async_update(self) -> None:
        """Update station state."""
        _LOGGER.debug(
            "Updating CityBikes station %s in network %s (entity_id=%s)",
            self._station_id,
            self._network.network_id,
            self.entity_id,
        )
        station_data = {}
        for station in self._network.stations:
            if station[ATTR_ID] == self._station_id:
                station_data = station
                break
        self._attr_name = station_data.get(ATTR_NAME)
        self._attr_native_value = station_data.get(ATTR_FREE_BIKES)
        self._attr_extra_state_attributes = {
            ATTR_UID: station_data.get(ATTR_EXTRA, {}).get(ATTR_UID),
            ATTR_LATITUDE: station_data.get(ATTR_LATITUDE),
            ATTR_LONGITUDE: station_data.get(ATTR_LONGITUDE),
            ATTR_EMPTY_SLOTS: station_data.get(ATTR_EMPTY_SLOTS),
            ATTR_TIMESTAMP: station_data.get(ATTR_TIMESTAMP),
        }
