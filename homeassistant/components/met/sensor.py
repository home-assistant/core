"""Support for Met sensor platform."""
import asyncio
import logging
from random import randrange
from xml.parsers.expat import ExpatError

import aiohttp
import async_timeout
import xmltodict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later, async_track_utc_time_change
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util

from .const import (
    API_URL,
    ATTRIBUTION,
    CONF_FORECAST,
    DEFAULT_FORECAST,
    DEFAULT_NAME,
    SENSOR_TYPE_CLASS,
    SENSOR_TYPE_NAME,
    SENSOR_TYPE_UNIT,
    SENSOR_TYPES,
    SYMBOL_API_URL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up the Met sensor platform."""
    _LOGGER.warning("Loading Met.no via platform config is deprecated")
    pass


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> bool:
    """Set up the Met sensor from a config entry."""
    elevation = entry.data.get(CONF_ELEVATION, hass.config.elevation or 0)
    forecast = entry.data.get(CONF_FORECAST, DEFAULT_FORECAST)
    latitude = entry.data.get(CONF_LATITUDE, hass.config.latitude)
    longitude = entry.data.get(CONF_LONGITUDE, hass.config.longitude)
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    coordinates = {
        "lat": str(latitude),
        "lon": str(longitude),
        "msl": str(elevation),
    }

    entities = []
    for sensor_type in SENSOR_TYPES:
        entities.append(MetSensor(name, sensor_type))
    async_add_entities(entities)

    weather = MetData(hass, coordinates, forecast, entities)
    async_track_utc_time_change(hass, weather.updating_devices, minute=31, second=0)
    await weather.fetching_data()
    return True


class MetSensor(Entity):
    """Representation of an Met sensor."""

    def __init__(self, name: str, sensor_type: str):
        """Initialize the sensor."""
        self.type = sensor_type
        self._name = f"{name} {SENSOR_TYPES[self.type][SENSOR_TYPE_NAME]}"
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[self.type][SENSOR_TYPE_UNIT]
        self._device_class = SENSOR_TYPES[self.type][SENSOR_TYPE_CLASS]

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def entity_picture(self):
        """Weather symbol if type is symbol."""
        if self.type != "symbol":
            return None
        return SYMBOL_API_URL.format(self._state)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the device class of this entity, if any."""
        return self._device_class


class MetData:
    """Get the latest data and updates the states."""

    def __init__(self, hass, coordinates, forecast, devices):
        """Initialize the data object."""
        self._urlparams = coordinates
        self._forecast = forecast
        self.devices = devices
        self.data = {}
        self.hass = hass

    async def fetching_data(self, *_):
        """Get the latest data from Met.no."""

        def try_again(err: str):
            """Retry in 15 to 20 minutes."""
            minutes = 15 + randrange(6)
            _LOGGER.error("Retrying in %i minutes: %s", minutes, err)
            async_call_later(self.hass, minutes * 60, self.fetching_data)

        try:
            websession = async_get_clientsession(self.hass)
            with async_timeout.timeout(10):
                resp = await websession.get(API_URL, params=self._urlparams)
            if resp.status != 200:
                try_again(f"{resp.url} returned {resp.status}")
                return
            text = await resp.text()

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            try_again(err)
            return

        try:
            self.data = xmltodict.parse(text)["weatherdata"]
        except (ExpatError, IndexError) as err:
            try_again(err)
            return

        await self.updating_devices()
        async_call_later(self.hass, 60 * 60, self.fetching_data)

    async def updating_devices(self, *_):
        """Find the current data from self.data."""
        if not self.data:
            return

        now = dt_util.utcnow()
        forecast_time = now + dt_util.dt.timedelta(hours=self._forecast)

        # Find the correct time entry. Since not all time entries contain all
        # types of data, we cannot just select one. Instead, we order  them by
        # distance from the desired forecast_time, and for every device iterate
        # them in order of increasing distance, taking the first time_point
        # that contains the desired data.

        ordered_entries = []

        for time_entry in self.data["product"]["time"]:
            valid_from = dt_util.parse_datetime(time_entry["@from"])
            valid_to = dt_util.parse_datetime(time_entry["@to"])

            if now >= valid_to:
                # Has already passed. Never select this.
                continue

            average_dist = abs((valid_to - forecast_time).total_seconds()) + abs(
                (valid_from - forecast_time).total_seconds()
            )

            ordered_entries.append((average_dist, time_entry))

        ordered_entries.sort(key=lambda item: item[0])

        # Update all devices
        tasks = []
        if ordered_entries:
            for dev in self.devices:
                new_state = None

                for (_, selected_time_entry) in ordered_entries:
                    loc_data = selected_time_entry["location"]

                    if dev.type not in loc_data:
                        continue

                    if dev.type == "precipitation":
                        new_state = loc_data[dev.type]["@value"]
                    elif dev.type == "symbol":
                        new_state = loc_data[dev.type]["@number"]
                    elif dev.type in (
                        "temperature",
                        "pressure",
                        "humidity",
                        "dewpointTemperature",
                    ):
                        new_state = loc_data[dev.type]["@value"]
                    elif dev.type in ("windSpeed", "windGust"):
                        new_state = loc_data[dev.type]["@mps"]
                    elif dev.type == "windDirection":
                        new_state = float(loc_data[dev.type]["@deg"])
                    elif dev.type in (
                        "fog",
                        "cloudiness",
                        "lowClouds",
                        "mediumClouds",
                        "highClouds",
                    ):
                        new_state = loc_data[dev.type]["@percent"]

                    break

                # pylint: disable=protected-access
                if new_state != dev._state:
                    dev._state = new_state
                    tasks.append(dev.async_update_ha_state())

        if tasks:
            await asyncio.wait(tasks)
