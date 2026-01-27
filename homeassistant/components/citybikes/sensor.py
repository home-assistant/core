"""Sensor for the CityBikes data."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import sys

import aiohttp
from citybikes import __version__ as CITYBIKES_CLIENT_VERSION
from citybikes.asyncio import Client as CitybikesClient
import voluptuous as vol

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import (
    APPLICATION_NAME,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
    EVENT_HOMEASSISTANT_CLOSE,
    UnitOfLength,
    __version__,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import location as location_util
from homeassistant.util.unit_conversion import DistanceConverter
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

_LOGGER = logging.getLogger(__name__)

HA_USER_AGENT = (
    f"{APPLICATION_NAME}/{__version__} "
    f"python-citybikes/{CITYBIKES_CLIENT_VERSION} "
    f"Python/{sys.version_info[0]}.{sys.version_info[1]}"
)

ATTR_UID = "uid"
ATTR_LATITUDE = "latitude"
ATTR_LONGITUDE = "longitude"
ATTR_EMPTY_SLOTS = "empty_slots"
ATTR_TIMESTAMP = "timestamp"

CONF_NETWORK = "network"
CONF_STATIONS_LIST = "stations"

PLATFORM = "citybikes"

MONITORED_NETWORKS = "monitored-networks"

DATA_CLIENT = "client"

NETWORKS_URI = "v2/networks"

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=5)

SCAN_INTERVAL = timedelta(minutes=5)  # Timely, and doesn't suffocate the API

CITYBIKES_ATTRIBUTION = (
    "Information provided by the CityBikes Project (https://citybik.es/#about)"
)

CITYBIKES_NETWORKS = "citybikes_networks"

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_RADIUS, CONF_STATIONS_LIST),
    SENSOR_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_NAME, default=""): cv.string,
            vol.Optional(CONF_NETWORK): cv.string,
            vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
            vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
            vol.Optional(CONF_RADIUS, "station_filter"): cv.positive_int,
            vol.Optional(CONF_STATIONS_LIST, "station_filter"): vol.All(
                cv.ensure_list, vol.Length(min=1), [cv.string]
            ),
        }
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the CityBikes platform."""
    if PLATFORM not in hass.data:
        hass.data[PLATFORM] = {MONITORED_NETWORKS: {}}

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    network_id = config.get(CONF_NETWORK)
    stations_list = set(config.get(CONF_STATIONS_LIST, []))
    radius = config.get(CONF_RADIUS, 0)
    name = config[CONF_NAME]
    if hass.config.units is US_CUSTOMARY_SYSTEM:
        radius = DistanceConverter.convert(
            radius, UnitOfLength.FEET, UnitOfLength.METERS
        )

    client = CitybikesClient(user_agent=HA_USER_AGENT, timeout=REQUEST_TIMEOUT)
    hass.data[PLATFORM][DATA_CLIENT] = client

    async def _async_close_client(event):
        await client.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_client)

    # Create a single instance of CityBikesNetworks.
    networks = hass.data.setdefault(CITYBIKES_NETWORKS, CityBikesNetworks(hass))

    if not network_id:
        network_id = await networks.get_closest_network_id(latitude, longitude)

    if network_id not in hass.data[PLATFORM][MONITORED_NETWORKS]:
        network = CityBikesNetwork(hass, network_id)
        hass.data[PLATFORM][MONITORED_NETWORKS][network_id] = network
        hass.async_create_task(network.async_refresh())
        async_track_time_interval(hass, network.async_refresh, SCAN_INTERVAL)
    else:
        network = hass.data[PLATFORM][MONITORED_NETWORKS][network_id]

    await network.ready.wait()

    devices = []
    for station in network.stations:
        dist = location_util.distance(
            latitude, longitude, station.latitude, station.longitude
        )
        station_id = station.id
        station_uid = str(station.extra.get(ATTR_UID, ""))

        if radius > dist or stations_list.intersection((station_id, station_uid)):
            if name:
                uid = f"{network.network_id}_{name}_{station_id}"
            else:
                uid = f"{network.network_id}_{station_id}"
            entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, uid, hass=hass)
            devices.append(CityBikesStation(network, station_id, entity_id))

    async_add_entities(devices, True)


class CityBikesNetworks:
    """Represent all CityBikes networks."""

    def __init__(self, hass):
        """Initialize the networks instance."""
        self.hass = hass
        self.client = hass.data[PLATFORM][DATA_CLIENT]
        self.networks = None
        self.networks_loading = asyncio.Condition()

    async def get_closest_network_id(self, latitude, longitude):
        """Return the id of the network closest to provided location."""
        try:
            await self.networks_loading.acquire()
            if self.networks is None:
                self.networks = await self.client.networks.fetch()
        except aiohttp.ClientError as err:
            raise PlatformNotReady from err
        else:
            result = None
            minimum_dist = None
            for network in self.networks:
                network_latitude = network.location.latitude
                network_longitude = network.location.longitude
                dist = location_util.distance(
                    latitude, longitude, network_latitude, network_longitude
                )
                if minimum_dist is None or dist < minimum_dist:
                    minimum_dist = dist
                    result = network.id

            return result
        finally:
            self.networks_loading.release()


class CityBikesNetwork:
    """Thin wrapper around a CityBikes network object."""

    def __init__(self, hass, network_id):
        """Initialize the network object."""
        self.hass = hass
        self.network_id = network_id
        self.stations = []
        self.ready = asyncio.Event()
        self.client = hass.data[PLATFORM][DATA_CLIENT]

    async def async_refresh(self, now=None):
        """Refresh the state of the network."""
        try:
            network = await self.client.network(uid=self.network_id).fetch()
        except aiohttp.ClientError as err:
            if now is None:
                raise PlatformNotReady from err
            self.ready.clear()
            return

        self.stations = network.stations
        self.ready.set()


class CityBikesStation(SensorEntity):
    """CityBikes API Sensor."""

    _attr_attribution = CITYBIKES_ATTRIBUTION
    _attr_native_unit_of_measurement = "bikes"
    _attr_icon = "mdi:bike"

    def __init__(self, network, station_id, entity_id):
        """Initialize the sensor."""
        self._network = network
        self._station_id = station_id
        self.entity_id = entity_id

    async def async_update(self) -> None:
        """Update station state."""
        station = next(s for s in self._network.stations if s.id == self._station_id)
        self._attr_name = station.name
        self._attr_native_value = station.free_bikes
        self._attr_extra_state_attributes = {
            ATTR_UID: station.extra.get(ATTR_UID),
            ATTR_LATITUDE: station.latitude,
            ATTR_LONGITUDE: station.longitude,
            ATTR_EMPTY_SLOTS: station.empty_slots,
            ATTR_TIMESTAMP: station.timestamp,
        }
