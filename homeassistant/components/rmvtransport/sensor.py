"""Support for departure information for Rhein-Main public transport."""
import asyncio
import logging

from homeassistant.const import (
    CONF_NAME,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_SHOW_ON_MAP,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle, slugify

from . import (
    DATA_RMVTRANSPORT_CLIENT,
    DEFAULT_NAME,
    CONF_TIMEOUT,
    CONF_STATION,
    CONF_DESTINATIONS,
    CONF_DIRECTION,
    CONF_LINES,
    CONF_PRODUCTS,
    CONF_TIME_OFFSET,
    CONF_MAX_JOURNEYS,
    CONF_NEXT_DEPARTURE,
    ICONS,
    RMVDepartureData,
)
from .const import (
    DOMAIN,
    DEFAULT_MAX_JOURNEYS,
    DEFAULT_TIME_OFFSET,
    DEFAULT_TIMEOUT,
    VALID_PRODUCTS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the RMV departure sensor."""
    timeout = config.get(CONF_TIMEOUT)

    session = async_get_clientsession(hass)

    sensors = []
    for next_departure in config.get(CONF_NEXT_DEPARTURE):
        sensors.append(
            RMVDepartureSensor(
                session,
                next_departure[CONF_STATION],
                next_departure.get(CONF_DESTINATIONS, []),
                next_departure.get(CONF_DIRECTION),
                next_departure.get(CONF_LINES, []),
                next_departure.get(CONF_PRODUCTS, VALID_PRODUCTS),
                next_departure.get(CONF_TIME_OFFSET, DEFAULT_TIME_OFFSET),
                next_departure.get(CONF_MAX_JOURNEYS, DEFAULT_MAX_JOURNEYS),
                next_departure.get(CONF_NAME),
                timeout,
                next_departure.get(CONF_SHOW_ON_MAP, False),
            )
        )

    tasks = [sensor.async_update() for sensor in sensors]
    if tasks:
        await asyncio.wait(tasks)
    if not all(sensor.data.departures for sensor in sensors):
        raise PlatformNotReady

    async_add_entities(sensors)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a RMV departure sensor based on a config entry."""
    timeout = entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

    session = async_get_clientsession(hass)

    rmv_rata = RMVDepartureSensor(
        session,
        entry.data[CONF_STATION],
        entry.data.get(CONF_DESTINATIONS, []),
        entry.data.get(CONF_DIRECTION),
        entry.data.get(CONF_LINES, []),
        entry.data.get(CONF_PRODUCTS),
        entry.data.get(CONF_TIME_OFFSET, DEFAULT_TIME_OFFSET),
        entry.data.get(CONF_MAX_JOURNEYS, DEFAULT_MAX_JOURNEYS),
        entry.title,
        timeout,
        entry.data.get(CONF_SHOW_ON_MAP),
    )
    await rmv_rata.async_update()
    hass.data[DOMAIN][DATA_RMVTRANSPORT_CLIENT][entry.entry_id] = rmv_rata

    async_add_entities([rmv_rata])


class RMVDepartureSensor(Entity):
    """Implementation of an RMV departure sensor."""

    def __init__(
        self,
        session,
        station,
        destinations,
        direction,
        lines,
        products,
        time_offset,
        max_journeys,
        name,
        timeout,
        show_on_map=False,
    ):
        """Initialize the sensor."""
        self._station = station
        self._name = name
        self._state = None
        self.data = RMVDepartureData(
            session,
            station,
            destinations,
            direction,
            lines,
            products,
            time_offset,
            max_journeys,
            timeout,
        )
        self._show_on_map = show_on_map
        self._icon = ICONS[None]
        self._uniqueid = slugify(
            f"s{station}-d{direction}-l{''.join(lines)}-"
            f"p{''.join(products)}-t{time_offset}-mj{max_journeys}-{name}"
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def state(self):
        """Return the next departure time."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        try:
            attrs = {
                "next_departures": [val for val in self.data.departures[1:]],
                "direction": self.data.departures[0].get("direction"),
                "line": self.data.departures[0].get("line"),
                "minutes": self.data.departures[0].get("minutes"),
                "departure_time": self.data.departures[0].get("departure_time"),
                "product": self.data.departures[0].get("product"),
            }
            on_map = ATTR_LATITUDE, ATTR_LONGITUDE
            no_map = "lat", "long"
            lat_format, lon_format = on_map if self._show_on_map else no_map
            try:
                attrs[lon_format] = self.data.station_info["long"]
                attrs[lat_format] = self.data.station_info["lat"]
            except (KeyError, TypeError):
                pass

            return attrs
        except IndexError:
            return {}

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            "next_departures": [val for val in self.data.departures[1:]],
            "direction": self.data.departures[0].get("direction"),
            "line": self.data.departures[0].get("line"),
            "product": self.data.departures[0].get("product"),
        }

    @property
    def unique_id(self):
        """Return a unique identifier for this device."""
        return self._uniqueid

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return "min"

    async def async_update(self):
        """Get the latest data and update the state."""
        await self.data.async_update()

        if not self.data.departures:
            self._state = None
            self._icon = ICONS[None]
            return
        if self._name == DEFAULT_NAME:
            self._name = self.data.station
        self._station = self.data.station
        self._state = self.data.departures[0].get("minutes")
        self._icon = ICONS[self.data.departures[0].get("product")]
