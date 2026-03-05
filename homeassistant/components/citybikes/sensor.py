"""Sensor for the CityBikes data."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import sys

import aiohttp
from citybikes import __version__ as CITYBIKES_CLIENT_VERSION
from citybikes.asyncio import Client as CitybikesClient
from citybikes.model import (
    Network as CitybikesNetworkModel,
    Station as CitybikesStationModel,
)

from homeassistant.components.sensor import ENTITY_ID_FORMAT, SensorEntity
from homeassistant.config_entries import ConfigEntry
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
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
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
    stations_list = set(config_entry.data.get(CONF_STATIONS_LIST, []) or [])
    radius = config_entry.data.get(CONF_RADIUS, 0)
    name = config_entry.data.get(CONF_NAME)
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
    networks: CityBikesNetworks = hass.data.setdefault(
        CITYBIKES_NETWORKS, CityBikesNetworks(hass)
    )

    if not network_id:
        network_id = await networks.get_closest_network_id(latitude, longitude)

    network: CityBikesNetwork
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
            latitude, longitude, station.latitude, station.longitude
        )
        station_id = station.id
        station_uid = str(station.extra.get(ATTR_UID, ""))

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

    def __init__(
        self, hass: HomeAssistant, client: CitybikesClient | None = None
    ) -> None:
        """Initialize the networks instance."""
        self.hass = hass
        self.client = client or hass.data[PLATFORM][DATA_CLIENT]
        self.networks: list[CitybikesNetworkModel] | None = None
        self.networks_loading = asyncio.Condition()

    async def load_networks(self):
        """Load the list of networks from the CityBikes API."""
        try:
            await self.networks_loading.acquire()
            if self.networks is None:
                self.networks = await self.client.networks.fetch()
        except aiohttp.ClientError as err:
            raise PlatformNotReady from err
        finally:
            self.networks_loading.release()
        return self.networks

    async def get_closest_network_id(self, latitude, longitude) -> str:
        """Return the id of the network closest to provided location."""
        await self.load_networks()
        if self.networks is None:
            raise PlatformNotReady
        result: str | None = None
        minimum_dist = None
        for network in self.networks:
            network_latitude = network.location.latitude
            network_longitude = network.location.longitude
            dist = location_util.distance(
                latitude, longitude, network_latitude, network_longitude
            )
            if dist is not None and (minimum_dist is None or dist < minimum_dist):
                minimum_dist = dist
                result = network.id
        # should not be possible, but this satisfies the type checker
        if result is None:
            _LOGGER.error(
                "Unable to find a CityBikes network close to the provided location lat=%s, lon=%s",
                str(latitude),
                str(longitude),
            )
            raise ValueError("No CityBikes networks found")
        return result


class CityBikesNetwork:
    """Thin wrapper around a CityBikes network object."""

    def __init__(
        self,
        hass: HomeAssistant,
        network_id: str,
        client: CitybikesClient | None = None,
    ) -> None:
        """Initialize the network object."""
        self.hass = hass
        self.network_id = network_id
        self.stations: list[CitybikesStationModel] = []
        self.ready = asyncio.Event()
        self.client: CitybikesClient = client or hass.data[PLATFORM][DATA_CLIENT]

    async def async_refresh(self, now=None) -> None:
        """Refresh the state of the network."""
        _LOGGER.debug("Refreshing CityBikes network %s", self.network_id)
        try:
            network: CitybikesNetworkModel = await self.client.network(
                uid=self.network_id
            ).fetch()
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
